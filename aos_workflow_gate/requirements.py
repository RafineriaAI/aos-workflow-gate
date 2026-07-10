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

from typing import Any

from .checkpr import (
    fetch_branch_rules,
    fetch_commit_statuses,
    required_checks_from_rules,
    rules_digest,
    strict_policy_from_rules,
)
from .collect import Budget, wait_for_required

SATISFIED = "satisfied"
FAILED = "failed"
PENDING = "pending"
MISSING = "missing"
UNVERIFIABLE = "unverifiable"


def _run_app_id(run: dict[str, Any]) -> int | None:
    app = run.get("app")
    if isinstance(app, dict) and isinstance(app.get("id"), int):
        return app["id"]
    return None


def classify_control(
    control: dict[str, Any],
    runs: list[dict[str, Any]],
    statuses: list[dict[str, Any]],
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
) -> dict[str, Any]:
    """Build the shared, SHA-pinned requirement snapshot.

    Fetches the branch's active rules, polls the head's check runs until
    the required contexts complete (within the wait budget; pagination
    followed within the page budget), fetches legacy commit statuses,
    and classifies every required control. Everything is pinned to the
    exact ``sha`` passed in — the snapshot never resolves refs itself.
    """
    rules = fetch_branch_rules(
        api_url, slug, branch, token=token, budget=budget
    )
    controls = required_checks_from_rules(rules)
    required_ids = [control["context"] for control in controls]

    runs, truncated, incomplete, waited = wait_for_required(
        repository, sha, required_ids,
        token=token, api_url=api_url,
        wait_seconds=wait_seconds, poll_interval=poll_interval,
        budget=budget,
    )
    statuses = fetch_commit_statuses(
        api_url, slug, sha, token=token, budget=budget
    )
    classified = [
        classify_control(control, runs, statuses) for control in controls
    ]
    return {
        "sha": sha,
        "branch": branch,
        "rules": rules,
        "rules_digest": rules_digest(rules),
        "strict_up_to_date_required": strict_policy_from_rules(rules),
        "controls": classified,
        "required_ids": required_ids,
        "runs": runs,
        "qualifying_runs": qualifying_runs(runs, controls),
        "statuses": statuses,
        "truncated": truncated,
        "incomplete_required": incomplete,
        "waited_seconds": waited,
    }


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
