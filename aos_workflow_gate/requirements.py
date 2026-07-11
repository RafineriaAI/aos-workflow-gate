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
"""

from __future__ import annotations

import os
from typing import Any

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
        return {**control, "state": state, "observed": observed}
    if unfinished:
        return {**control, "state": PENDING, "observed": observed}

    if status_qualifying:
        raw_states = [
            str(status.get("state", "unknown")).lower()
            for status in status_qualifying
        ]
        observed["legacy_state"] = raw_states[0]
        if "success" in raw_states:
            state = SATISFIED
        elif "pending" in raw_states:
            state = PENDING
        else:
            state = FAILED
        return {**control, "state": state, "observed": observed}

    if imposters or (bound_app is not None and named_statuses):
        if bound_app is not None and named_statuses and not imposters:
            observed["legacy_status_cannot_prove_app"] = True
        return {**control, "state": UNVERIFIABLE, "observed": observed}
    if bound_app is None and not statuses_readable:
        # the stream that could have satisfied this control was not
        # readable: unknown is stated as unverifiable, never as absent
        observed["statuses_stream"] = "unreadable"
        return {**control, "state": UNVERIFIABLE, "observed": observed}
    return {**control, "state": MISSING, "observed": observed}


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
) -> tuple[bool, list[dict[str, Any]], bool]:
    """Classic branch protection fallback (pre-rulesets repositories).

    Reads the branch object: ``protected`` is visible with read access;
    the ``protection.required_status_checks.checks`` details (context +
    enforcing ``app_id``) are only exposed to users with push access.
    Returns ``(protected, controls, details_available)`` — a protected
    branch whose details are not visible must be reported as such, never
    treated as unprotected.
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
    if not protected or not isinstance(protection, dict):
        return protected, [], isinstance(protection, dict)
    rsc = protection.get("required_status_checks")
    if not isinstance(rsc, dict):
        return protected, [], True
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
    return protected, [controls[key] for key in sorted(controls)], True


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
    controls = required_checks_from_rules(rules)
    protection_source = "rulesets" if controls else "none"
    classic_note: str | None = None
    if not controls:
        # classic branch protection fallback: rulesets are the modern
        # source, but pre-ruleset repositories still express required
        # checks through classic protection
        try:
            protected, classic_controls, details = fetch_classic_protection(
                api_url, slug, branch, token=token, budget=budget
            )
            if classic_controls:
                controls = classic_controls
                protection_source = "classic_branch_protection"
            elif protected and not details:
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
                }
            )
            continue
        classified.append(
            classify_control(
                control, runs, statuses,
                statuses_readable=statuses_unverifiable is None,
            )
        )
    snapshot: dict[str, Any] = {
        "sha": sha,
        "branch": branch,
        "rules": rules,
        "rules_digest": rules_digest(rules),
        "strict_up_to_date_required": strict_policy_from_rules(rules),
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
    """Compact per-control evidence for the bundle's collection object."""
    return [
        {
            "context": control["context"],
            "integration_id": control.get("integration_id"),
            "state": control["state"],
        }
        for control in controls
    ]
