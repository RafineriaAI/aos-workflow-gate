"""Shared GitHub requirement snapshot.

One canonical, SHA-pinned observation of what GitHub requires and what
actually ran: the base branch's ACTIVE rules (required status checks
with app-bound identity), the head's check runs (paginated), and the
head's legacy commit statuses. Commands build on the same snapshot, so
requirement semantics cannot drift between entry points.

Scope: **required status checks only** — deliberately not full
merge-readiness. Reviews, deployments, merge conflicts, and rule bypass
actors are out of scope and stated as such wherever the snapshot is
rendered.

Each required control is classified into exactly one state:

- ``satisfied``    — a qualifying observation concluded ``success``;
- ``failed``       — a qualifying observation concluded non-success;
- ``pending``      — a qualifying observation exists but has not
                     finished;
- ``missing``      — nothing with that context exists on the head SHA;
- ``unverifiable`` — something with that context exists, but it cannot
                     be shown to satisfy the requirement: the rules bind
                     the check to a specific app (``integration_id``)
                     and the observation comes from a different or
                     unidentifiable app, or only a legacy commit status
                     exists, which carries no app identity at all.

App-bound check identity is enforced, not assumed: a check run only
*qualifies* for an app-bound requirement when its reported app id
equals the required ``integration_id``. A same-named run from another
app can no longer satisfy the requirement — it is evidence of the
mismatch instead. The classification travels in the bundle's collection
object (``requirements``), so ``missing``/``pending``/``unverifiable``
are recorded as digest-anchored evidence, never silently.

Dual-track semantics: GitHub treats ``neutral`` and ``skipped``
conclusions as passing for required status checks; this gate does not
(evidence that never ran is not evidence). Both readings are recorded:
``state`` is the gate's evidence state (only ``success`` satisfies) and
``github_equivalent`` is what GitHub's own semantics would do with the
same observation (``would_pass``/``would_fail``/``would_wait``/
``unknown``). Raw conclusions stay verbatim in ``observed`` — the
normalization never overwrites the source value, so neither reading
misrepresents the other.

Protection sources are merged, not chosen: GitHub enforces rulesets and
classic branch protection simultaneously when both are active, so the
snapshot reads both and takes the union of required contexts; each
control records which mechanism(s) require it (``required_by``).
"""

from __future__ import annotations

import os
from typing import Any

from . import canonical
from .checkpr import (
    fetch_branch_rules,
    fetch_commit_statuses,
    required_checks_from_rules,
    rules_digest,
    strict_policy_from_rules,
)
from .collect import Budget, _request_json, fetch_check_runs, wait_for_required
from .errors import InputError

SATISFIED = "satisfied"
FAILED = "failed"
PENDING = "pending"
MISSING = "missing"
UNVERIFIABLE = "unverifiable"
SELF_REFERENCE = "self_reference"

# GitHub's own semantics for required status checks: neutral and skipped
# conclusions are treated as passing. This set normalizes conclusions
# for the github_equivalent track only; the gate's evidence state keeps
# requiring an actual 'success'.
GITHUB_PASSING_CONCLUSIONS = frozenset({"success", "neutral", "skipped"})

WOULD_PASS = "would_pass"
WOULD_FAIL = "would_fail"
WOULD_WAIT = "would_wait"
UNKNOWN = "unknown"


def _run_app_id(run: dict[str, Any]) -> int | None:
    app = run.get("app")
    if isinstance(app, dict) and isinstance(app.get("id"), int):
        return app["id"]
    return None


def classify_control(
    control: dict[str, Any],
    runs: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
    *,
    statuses_readable: bool = True,
) -> dict[str, Any]:
    """Classify one required control against observed runs and statuses.

    Qualification is identity-based: when the control declares an
    ``integration_id``, only a run reporting the same app id qualifies;
    legacy statuses never qualify for app-bound controls because the
    Status API carries no app identity. Within qualifying observations,
    the best available outcome wins (success over unfinished over
    failure is NOT how gates think — a completed conclusion is the
    outcome; an unfinished run is ``pending``).

    Every classification carries ``github_equivalent``: the outcome
    GitHub's own required-status-check semantics would produce for the
    same observation (neutral/skipped count as passing there). The raw
    conclusion stays in ``observed`` so neither track loses the source
    value.
    """
    context = control["context"]
    bound_app = control.get("integration_id")

    named_runs = [
        run for run in runs
        if isinstance(run.get("name"), str) and run["name"] == context
    ]
    named_statuses = [
        status for status in statuses
        if status.get("context") == context
    ]

    if bound_app is not None:
        qualifying = [
            run for run in named_runs if _run_app_id(run) == bound_app
        ]
        imposters = [
            run for run in named_runs if _run_app_id(run) != bound_app
        ]
        status_qualifying: list[dict[str, Any]] = []
    else:
        qualifying = named_runs
        imposters = []
        status_qualifying = named_statuses

    observed: dict[str, Any] = {}
    if imposters:
        observed["nonqualifying_app_ids"] = sorted(
            {
                (_run_app_id(run) if _run_app_id(run) is not None else -1)
                for run in imposters
            }
        )

    completed = [
        run for run in qualifying if run.get("status") == "completed"
    ]
    unfinished = [
        run for run in qualifying if run.get("status") != "completed"
    ]

    if completed:
        latest = max(
            completed, key=lambda run: str(run.get("completed_at") or "")
        )
        conclusion = latest.get("conclusion")
        observed["conclusion"] = conclusion
        observed["app_id"] = _run_app_id(latest)
        state = SATISFIED if conclusion == "success" else FAILED
        equivalent = (
            WOULD_PASS
            if conclusion in GITHUB_PASSING_CONCLUSIONS
            else WOULD_FAIL
        )
        return {
            **control, "state": state, "observed": observed,
            "github_equivalent": equivalent,
        }
    if unfinished:
        return {
            **control, "state": PENDING, "observed": observed,
            "github_equivalent": WOULD_WAIT,
        }

    if status_qualifying:
        raw_states = [
            str(status.get("state", "unknown")).lower()
            for status in status_qualifying
        ]
        observed["legacy_state"] = raw_states[0]
        if "success" in raw_states:
            state, equivalent = SATISFIED, WOULD_PASS
        elif "pending" in raw_states:
            state, equivalent = PENDING, WOULD_WAIT
        else:
            state, equivalent = FAILED, WOULD_FAIL
        return {
            **control, "state": state, "observed": observed,
            "github_equivalent": equivalent,
        }

    if imposters or (bound_app is not None and named_statuses):
        if bound_app is not None and named_statuses and not imposters:
            observed["legacy_status_cannot_prove_app"] = True
        # GitHub enforces the same app binding: the requirement stays
        # "Expected" there until the bound app reports
        return {
            **control, "state": UNVERIFIABLE, "observed": observed,
            "github_equivalent": WOULD_WAIT,
        }
    if bound_app is None and not statuses_readable:
        # the stream that could have satisfied this control was not
        # readable: unknown is stated as unverifiable, never as absent
        observed["statuses_stream"] = "unreadable"
        return {
            **control, "state": UNVERIFIABLE, "observed": observed,
            "github_equivalent": UNKNOWN,
        }
    # a missing required context shows as "Expected" on GitHub: the
    # merge waits for it, which is not the same as a failure
    return {
        **control, "state": MISSING, "observed": observed,
        "github_equivalent": WOULD_WAIT,
    }


def qualifying_runs(
    runs: list[dict[str, Any]], controls: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Drop runs that share an app-bound control's context but come from
    another app, so an imposter can never become the bundled source for
    a requirement it does not satisfy. Runs for non-required contexts
    pass through untouched."""
    bound = {
        control["context"]: control["integration_id"]
        for control in controls
        if control.get("integration_id") is not None
    }
    kept = []
    for run in runs:
        name = run.get("name")
        if isinstance(name, str) and name in bound:
            if _run_app_id(run) != bound[name]:
                continue
        kept.append(run)
    return kept


def fetch_classic_protection(
    api_url: str, slug: str, branch: str, *, token: str | None, budget: Budget
) -> dict[str, Any]:
    """Classic branch protection surface (read alongside rulesets).

    Reads the branch object: ``protected`` is visible with read access;
    the ``protection.required_status_checks.checks`` details (context +
    enforcing ``app_id``) are only exposed to users with push access.
    Returns ``{"protected", "controls", "details_available", "strict"}``
    — a protected branch whose details are not visible must be reported
    as such, never treated as unprotected.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = _request_json(
        f"{api_url}/repos/{slug}/branches/{branch}",
        headers,
        timeout=30.0,
        budget=budget,
        capability="branch_rules",
    )
    if not isinstance(payload, dict):
        raise InputError("branch API response is not a JSON object")
    protected = bool(payload.get("protected"))
    protection = payload.get("protection")
    result: dict[str, Any] = {
        "protected": protected,
        "controls": [],
        "details_available": isinstance(protection, dict),
        "strict": False,
    }
    if not protected or not isinstance(protection, dict):
        return result
    rsc = protection.get("required_status_checks")
    if not isinstance(rsc, dict):
        return result
    result["strict"] = bool(rsc.get("strict"))
    controls: dict[str, dict[str, Any]] = {}
    checks = rsc.get("checks")
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict) and isinstance(
                check.get("context"), str
            ):
                controls[check["context"]] = {
                    "context": check["context"],
                    "integration_id": check.get("app_id"),
                }
    for context in rsc.get("contexts") or []:
        if isinstance(context, str) and context not in controls:
            controls[context] = {"context": context, "integration_id": None}
    result["controls"] = [controls[key] for key in sorted(controls)]
    return result


RULESETS = "rulesets"
CLASSIC = "classic_branch_protection"


def merge_protection_controls(
    ruleset_controls: list[dict[str, Any]],
    classic_controls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Union of the two protection surfaces GitHub enforces together.

    A context required by both mechanisms is one control with both
    listed in ``required_by``; an app binding declared by either
    mechanism is kept (a control cannot lose its identity binding by
    also being required somewhere that does not declare one).
    """
    merged: dict[str, dict[str, Any]] = {}
    for control in ruleset_controls:
        merged[control["context"]] = {**control, "required_by": [RULESETS]}
    for control in classic_controls:
        context = control["context"]
        existing = merged.get(context)
        if existing is None:
            merged[context] = {**control, "required_by": [CLASSIC]}
            continue
        existing["required_by"].append(CLASSIC)
        if (
            existing.get("integration_id") is None
            and control.get("integration_id") is not None
        ):
            existing["integration_id"] = control["integration_id"]
    return [merged[key] for key in sorted(merged)]


def protection_digest(
    controls: list[dict[str, Any]], *, strict: bool
) -> str:
    """Canonical digest of the merged protection surface (drift primitive
    across rulesets AND classic protection; ``rules_digest`` remains the
    rulesets-only digest for compatibility with existing records)."""
    identity = {
        "controls": [
            {
                "context": control["context"],
                "integration_id": control.get("integration_id"),
                "required_by": control.get("required_by", []),
            }
            for control in controls
        ],
        "strict": strict,
    }
    return canonical.digest(identity)


def github_baseline(controls: list[dict[str, Any]]) -> str:
    """What GitHub's own required-status-check semantics would do.

    Scoped strictly to required status checks — this says nothing about
    reviews, deployments, conflicts, or bypass actors. Precedence:
    a failing control dominates, then an unknown one, then a waiting
    one; ``clear`` means every required control would pass on GitHub.
    """
    if not controls:
        return "no_required_checks"
    equivalents = {
        str(control.get("github_equivalent", UNKNOWN))
        for control in controls
    }
    if WOULD_FAIL in equivalents:
        return "blocked"
    if UNKNOWN in equivalents:
        return "unknown"
    if WOULD_WAIT in equivalents:
        return "waiting"
    return "clear"


def exclude_self_runs(
    runs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Drop check runs produced by the currently executing workflow run.

    A gate whose own check becomes required would otherwise wait for
    itself forever. The current run is identified by ``GITHUB_RUN_ID``
    in each check run's ``details_url``; excluded names are returned so
    the exclusion is recorded as evidence, never silent.
    """
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id:
        return runs, []
    marker = f"/runs/{run_id}/"
    kept: list[dict[str, Any]] = []
    excluded: list[str] = []
    for run in runs:
        details = run.get("details_url")
        if isinstance(details, str) and marker in details:
            name = run.get("name")
            excluded.append(name if isinstance(name, str) else "(unnamed)")
            continue
        kept.append(run)
    return kept, sorted(set(excluded))


def requirement_snapshot(
    *,
    api_url: str,
    slug: str,
    repository: str,
    sha: str,
    branch: str,
    token: str | None,
    budget: Budget,
    wait_seconds: float = 0.0,
    poll_interval: float = 10.0,
    exclude_self: bool = False,
) -> dict[str, Any]:
    """Build the shared, SHA-pinned requirement snapshot.

    Fetches the branch's active rules (with a classic branch-protection
    fallback), polls the head's check runs until the required contexts
    complete (within the wait budget; pagination followed within the
    page budget), fetches legacy commit statuses, and classifies every
    required control. Everything is pinned to the exact ``sha`` passed
    in — the snapshot never resolves refs itself.

    ``exclude_self`` resolves the self-reference problem: when the
    gate's own check has been made required, the current workflow run's
    checks are identified up front (one extra bounded listing), removed
    from the wait set and the bundleable runs, and their controls are
    classified ``self_reference`` — the gate never waits for itself and
    never grades itself, and the exclusion is recorded as evidence.
    """
    rules = fetch_branch_rules(
        api_url, slug, branch, token=token, budget=budget
    )
    ruleset_controls = required_checks_from_rules(rules)
    classic_note: str | None = None
    classic_controls: list[dict[str, Any]] = []
    classic_strict = False
    # both mechanisms enforce simultaneously when both are active, so
    # both are read on every snapshot and their contexts are unioned;
    # an unreadable classic surface degrades with a note, never silently
    try:
        classic = fetch_classic_protection(
            api_url, slug, branch, token=token, budget=budget
        )
        classic_controls = classic["controls"]
        classic_strict = classic["strict"]
        if classic["protected"] and not classic["details_available"]:
            classic_note = (
                "classic branch protection is enabled but its "
                "required-check details are not visible to this "
                "token (push access is needed); requirements are "
                "unverifiable, not absent"
            )
    except InputError as exc:
        classic_note = (
            f"classic branch protection could not be read: {exc}"
        )
    controls = merge_protection_controls(ruleset_controls, classic_controls)
    if ruleset_controls and classic_controls:
        protection_source = "rulesets+classic_branch_protection"
    elif ruleset_controls:
        protection_source = RULESETS
    elif classic_controls:
        protection_source = CLASSIC
    else:
        protection_source = "none"
    required_ids = [control["context"] for control in controls]

    self_names: list[str] = []
    if exclude_self and os.environ.get("GITHUB_RUN_ID"):
        initial_runs, _ = fetch_check_runs(
            repository, sha, token=token, api_url=api_url, budget=budget
        )
        _, self_names = exclude_self_runs(initial_runs)
    wait_ids = [name for name in required_ids if name not in self_names]

    runs, truncated, incomplete, waited = wait_for_required(
        repository, sha, wait_ids,
        token=token, api_url=api_url,
        wait_seconds=wait_seconds, poll_interval=poll_interval,
        budget=budget,
    )
    if exclude_self:
        runs, self_names = exclude_self_runs(runs)
    statuses_unverifiable: str | None = None
    try:
        statuses = fetch_commit_statuses(
            api_url, slug, sha, token=token, budget=budget
        )
    except InputError as exc:
        # the legacy status stream is non-essential: degrade instead of
        # aborting (can_continue: yes); affected unbound controls are
        # classified unverifiable, never silently missing
        statuses = []
        statuses_unverifiable = str(exc)
    classified = []
    for control in controls:
        if control["context"] in self_names:
            classified.append(
                {
                    **control,
                    "state": SELF_REFERENCE,
                    "observed": {
                        "note": "this is the gate's own check; it is "
                        "excluded from waiting and grading to avoid "
                        "self-reference"
                    },
                    # GitHub waits for the gate's own required check to
                    # report; it completes after this job does
                    "github_equivalent": WOULD_WAIT,
                }
            )
            continue
        classified.append(
            classify_control(
                control, runs, statuses,
                statuses_readable=statuses_unverifiable is None,
            )
        )
    merged_strict = strict_policy_from_rules(rules) or classic_strict
    snapshot: dict[str, Any] = {
        "sha": sha,
        "branch": branch,
        "rules": rules,
        "rules_digest": rules_digest(rules),
        "protection_digest": protection_digest(
            controls, strict=merged_strict
        ),
        "strict_up_to_date_required": merged_strict,
        "github_baseline": github_baseline(classified),
        "controls": classified,
        "required_ids": [
            name for name in required_ids if name not in self_names
        ],
        "self_reference_excluded": self_names,
        "runs": runs,
        "qualifying_runs": qualifying_runs(runs, controls),
        "statuses": statuses,
        "truncated": truncated,
        "incomplete_required": incomplete,
        "waited_seconds": waited,
        "protection_source": protection_source,
    }
    if classic_note is not None:
        snapshot["classic_protection_note"] = classic_note
    if statuses_unverifiable is not None:
        snapshot["statuses_unverifiable"] = statuses_unverifiable
    return snapshot


def requirement_evidence(
    controls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Compact per-control evidence for the bundle's collection object.

    Carries both tracks — the gate's evidence ``state`` and GitHub's
    ``github_equivalent`` — plus which protection mechanism(s) require
    the control, so a record can state a divergence ("GitHub would pass
    this; the evidence never ran") instead of implying agreement.
    """
    evidence = []
    for control in controls:
        entry: dict[str, Any] = {
            "context": control["context"],
            "integration_id": control.get("integration_id"),
            "state": control["state"],
        }
        if "github_equivalent" in control:
            entry["github_equivalent"] = control["github_equivalent"]
        if control.get("required_by"):
            entry["required_by"] = control["required_by"]
        evidence.append(entry)
    return evidence
