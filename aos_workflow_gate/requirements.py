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
conclusions as passing for required status checks. Both readings are
recorded: ``state`` is the literal evidence state (only ``success`` is
literal success) and ``github_equivalent`` is GitHub's interpretation
(``would_pass``/``would_fail``/``would_wait``/``unknown``). The generated
zero-config policy uses ``required_status_semantics: github``; an explicit
``success-only`` policy can require literal success. Raw conclusions stay
verbatim in ``observed`` and in the source, so policy interpretation never
rewrites evidence.

Protection sources are merged, not chosen: GitHub enforces rulesets and
classic branch protection simultaneously when both are active, so the
snapshot reads both and unions exact ``(context, integration_id)`` control
identities. ``required_by`` is deterministic provenance, not identity;
``repository + head_sha`` scopes the observation, not the requirement.
Different app bindings for one context remain separate controls.
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


def control_identity(control: dict[str, Any]) -> tuple[str, int | None]:
    """Return requirement identity, excluding provenance and scope."""
    return control["context"], control.get("integration_id")


def _identity_sort_key(
    identity: tuple[str, int | None],
) -> tuple[str, bool, int]:
    context, integration_id = identity
    return context, integration_id is not None, integration_id or -1


def _assign_source_ids(
    controls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Project control identities to deterministic policy source ids.

    A unique context retains its historical id. Only same-context controls
    with distinct app identities need a disambiguating suffix.
    """
    counts: dict[str, int] = {}
    for control in controls:
        context = control["context"]
        counts[context] = counts.get(context, 0) + 1

    assigned: list[dict[str, Any]] = []
    raw_contexts = set(counts)
    used: set[str] = set()
    for control in controls:
        context, integration_id = control_identity(control)
        source_id = context
        if counts[context] > 1:
            suffix = "any" if integration_id is None else str(integration_id)
            base = f"{context} [app:{suffix}]"
            source_id = base
            if source_id in raw_contexts or source_id in used:
                short_digest = canonical.digest(
                    {
                        "context": context,
                        "integration_id": integration_id,
                    }
                )[7:19]
                source_id = f"{base} [{short_digest}]"
                ordinal = 2
                while source_id in raw_contexts or source_id in used:
                    source_id = f"{base} [{short_digest}-{ordinal}]"
                    ordinal += 1
        if source_id in used:
            raise InputError(
                "required control source ids are not unique after "
                "identity projection"
            )
        used.add(source_id)
        assigned.append({**control, "source_id": source_id})
    return assigned


def legacy_status_source_ids(
    controls: list[dict[str, Any]],
) -> dict[str, str | None]:
    """Map contexts to the requirement a legacy status may prove.

    None means that every same-context requirement is app-bound. A legacy
    status carries no app identity and therefore cannot qualify.
    """
    by_context: dict[str, str | None] = {}
    for control in controls:
        context = control["context"]
        by_context.setdefault(context, None)
        if control.get("integration_id") is None:
            by_context[context] = str(control.get("source_id", context))
    return by_context


def _run_app_id(run: dict[str, Any]) -> int | None:
    app = run.get("app")
    if (
        isinstance(app, dict)
        and isinstance(app.get("id"), int)
        and not isinstance(app.get("id"), bool)
    ):
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
    """Bind runs to every qualifying control identity.

    One observation may satisfy both an unbound and an app-bound requirement.
    It is then projected to two digest-bound sources. Same-name imposters do
    not pass through; runs for non-required contexts do.
    """
    by_context: dict[str, list[dict[str, Any]]] = {}
    for control in controls:
        by_context.setdefault(control["context"], []).append(control)

    kept: list[dict[str, Any]] = []
    for run in runs:
        name = run.get("name")
        candidates = by_context.get(name) if isinstance(name, str) else None
        if not candidates:
            kept.append(run)
            continue
        app_id = _run_app_id(run)
        for control in candidates:
            bound_app = control.get("integration_id")
            if bound_app is not None and app_id != bound_app:
                continue
            projected = dict(run)
            projected["_aos_source_id"] = control.get(
                "source_id", control["context"]
            )
            projected["_aos_control_identity"] = {
                "context": control["context"],
                "integration_id": bound_app,
            }
            kept.append(projected)
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
    controls: dict[tuple[str, int | None], dict[str, Any]] = {}
    checked_contexts: set[str] = set()
    checks = rsc.get("checks")
    if isinstance(checks, list):
        for check in checks:
            if isinstance(check, dict) and isinstance(
                check.get("context"), str
            ):
                context = check["context"]
                integration_id = check.get("app_id")
                if integration_id is not None and (
                    not isinstance(integration_id, int)
                    or isinstance(integration_id, bool)
                ):
                    raise InputError(
                        "classic protection app_id must be an integer"
                    )
                checked_contexts.add(context)
                controls[(context, integration_id)] = {
                    "context": context,
                    "integration_id": integration_id,
                }
    for context in rsc.get("contexts") or []:
        # contexts is the legacy projection of checks in this same surface:
        # use it as fallback, not as a second requirement identity.
        if isinstance(context, str) and context not in checked_contexts:
            controls[(context, None)] = {
                "context": context,
                "integration_id": None,
            }
    result["controls"] = [
        controls[key] for key in sorted(controls, key=_identity_sort_key)
    ]
    return result


RULESETS = "rulesets"
CLASSIC = "classic_branch_protection"


def merge_protection_controls(
    ruleset_controls: list[dict[str, Any]],
    classic_controls: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Union of the two protection surfaces GitHub enforces together.

    Only an identical ``(context, integration_id)`` tuple is one control.
    ``required_by`` records deterministic provenance without changing
    identity. Same-context controls with different app bindings remain
    separate requirements.
    """
    merged: dict[tuple[str, int | None], dict[str, Any]] = {}
    for provenance, surface in (
        (RULESETS, ruleset_controls),
        (CLASSIC, classic_controls),
    ):
        for control in surface:
            identity = control_identity(control)
            existing = merged.get(identity)
            if existing is None:
                merged[identity] = {
                    **control,
                    "required_by": [provenance],
                }
            elif provenance not in existing["required_by"]:
                existing["required_by"].append(provenance)
    ordered = [
        merged[key] for key in sorted(merged, key=_identity_sort_key)
    ]
    return _assign_source_ids(ordered)


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


def incomplete_required_controls(
    controls: list[dict[str, Any]],
) -> list[str]:
    """Return controls still unresolved after every evidence stream.

    Check-run polling happens before the legacy Status API is read. The
    polling result is therefore provisional: an unbound requirement absent
    from Check Runs may still be satisfied by a successful commit status.
    Collection completeness must come from the final classifications.
    """
    unresolved = {PENDING, MISSING, UNVERIFIABLE}
    return sorted(
        str(control.get("source_id", control["context"]))
        for control in controls
        if control.get("state") in unresolved
    )


def _is_self_run(run: dict[str, Any]) -> bool:
    run_id = os.environ.get("GITHUB_RUN_ID")
    if not run_id:
        return False
    details = run.get("details_url")
    return (
        isinstance(details, str)
        and f"/runs/{run_id}/" in details
    )


def self_control_source_ids(
    runs: list[dict[str, Any]], controls: list[dict[str, Any]]
) -> list[str]:
    """Return only requirement identities produced by this workflow run."""
    source_ids: set[str] = set()
    for run in runs:
        if not _is_self_run(run):
            continue
        for control in controls:
            if run.get("name") != control["context"]:
                continue
            bound_app = control.get("integration_id")
            if bound_app is None or _run_app_id(run) == bound_app:
                source_ids.add(str(control["source_id"]))
    return sorted(source_ids)


def exclude_self_runs(
    runs: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Drop check runs produced by the currently executing workflow run.

    A gate whose own check becomes required would otherwise wait for
    itself forever. The current run is identified by ``GITHUB_RUN_ID``
    in each check run's ``details_url``; excluded names are returned so
    the exclusion is recorded as evidence, never silent.
    """
    kept: list[dict[str, Any]] = []
    excluded: list[str] = []
    for run in runs:
        if _is_self_run(run):
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
    # Both mechanisms enforce simultaneously when active, so both are
    # read and their exact control identities are unioned;
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
    required_ids = [str(control["source_id"]) for control in controls]

    self_source_ids: list[str] = []
    if exclude_self and os.environ.get("GITHUB_RUN_ID"):
        initial_runs, _ = fetch_check_runs(
            repository, sha, token=token, api_url=api_url, budget=budget
        )
        self_source_ids = self_control_source_ids(initial_runs, controls)
    wait_controls = [
        control for control in controls
        if control["source_id"] not in self_source_ids
    ]
    wait_ids = [str(control["source_id"]) for control in wait_controls]

    runs, truncated, _check_run_incomplete, waited = wait_for_required(
        repository, sha, wait_ids,
        token=token, api_url=api_url,
        wait_seconds=wait_seconds, poll_interval=poll_interval,
        budget=budget,
        required_controls=wait_controls,
    )
    if exclude_self:
        runs, _ = exclude_self_runs(runs)
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
    scoped_runs = [
        run for run in runs if run.get("head_sha") == sha
    ]
    subject_mismatch_runs = [
        run.get("id") for run in runs
        if run.get("head_sha") != sha
    ]

    for control in controls:
        if control["source_id"] in self_source_ids:
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
                control, scoped_runs, statuses,
                statuses_readable=statuses_unverifiable is None,
            )
        )
    incomplete = incomplete_required_controls(classified)
    merged_strict = strict_policy_from_rules(rules) or classic_strict
    snapshot: dict[str, Any] = {
        "sha": sha,
        "repository": repository,
        "observation_scope": {"repository": repository, "head_sha": sha},
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
            name for name in required_ids if name not in self_source_ids
        ],
        "self_reference_excluded": self_source_ids,
        "runs": scoped_runs,
        "qualifying_runs": qualifying_runs(scoped_runs, controls),
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
    if subject_mismatch_runs:
        snapshot["subject_mismatch_runs"] = subject_mismatch_runs
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
        source_id = control.get("source_id", control["context"])
        if source_id != control["context"]:
            entry["source_id"] = source_id
        if "github_equivalent" in control:
            entry["github_equivalent"] = control["github_equivalent"]
        if control.get("required_by"):
            entry["required_by"] = control["required_by"]
        evidence.append(entry)
    return evidence
