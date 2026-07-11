"""Workflow state and expected-run visibility.

Check runs only exist once a workflow job has started, so a workflow
that never started — awaiting fork approval (``action_required``),
queued behind concurrency limits, or waiting on an environment — is
invisible to a check-runs collector. This module reads the two streams
that do see it, both pinned to the exact commit SHA:

- **Check Suites** (``/commits/{sha}/check-suites``): every CI app's
  execution unit on the commit, whether or not any check run exists yet.
- **Workflow Runs** (``/actions/runs?head_sha={sha}``): GitHub Actions
  metadata (workflow name, event, run attempt) for suites that belong
  to Actions.

No double counting: the check suite is the unit of visibility. Workflow
runs are joined onto their suite by ``check_suite_id`` and only
*enrich* it; a workflow run whose suite was not listed (pagination
truncation) is added once, keyed by its suite id, never twice.

Visibility is evidence, never grading: nothing here creates a
``missing`` classification. A control is classified ``missing``
exclusively against an explicit expectation — a branch-rule control or
an operator-named required check (``expected_by``) — while this report
discloses what else existed on the commit and in which state
(``completed`` / ``pending`` / ``action_required``). An unreadable
stream degrades to ``available: false`` with the reason recorded,
never silently and never as a verdict.
"""

from __future__ import annotations

from typing import Any

from .collect import DEFAULT_API_URL, Budget, _request_json, validate_api_url
from .errors import InputError

COMPLETED = "completed"
PENDING = "pending"
ACTION_REQUIRED = "action_required"

_PER_PAGE = 100
_MAX_PAGES = 10


def _slug(repository: str) -> str:
    parts = repository.rstrip("/").rsplit("/", 2)
    return "/".join(parts[-2:]) if len(parts) >= 2 else repository


def _paginate(
    url_base: str,
    list_key: str,
    headers: dict[str, str],
    *,
    budget: Budget,
    capability: str,
) -> tuple[list[dict[str, Any]], bool]:
    collected: list[dict[str, Any]] = []
    total = 0
    for page in range(1, _MAX_PAGES + 1):
        separator = "&" if "?" in url_base else "?"
        payload = _request_json(
            f"{url_base}{separator}per_page={_PER_PAGE}&page={page}",
            headers,
            timeout=30.0,
            budget=budget,
            capability=capability,
        )
        if not isinstance(payload, dict):
            raise InputError(f"{capability} API response is not a JSON object")
        items = payload.get(list_key)
        page_items = (
            [item for item in items if isinstance(item, dict)]
            if isinstance(items, list)
            else []
        )
        raw_total = payload.get("total_count")
        total = raw_total if isinstance(raw_total, int) else total
        collected.extend(page_items)
        if len(page_items) < _PER_PAGE or len(collected) >= total:
            break
    return collected, total > len(collected)


def fetch_check_suites(
    repository: str,
    sha: str,
    *,
    token: str | None,
    api_url: str = DEFAULT_API_URL,
    budget: Budget | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Check suites for the exact commit; returns (suites, truncated)."""
    api_url = validate_api_url(api_url)
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return _paginate(
        f"{api_url}/repos/{_slug(repository)}/commits/{sha}/check-suites",
        "check_suites",
        headers,
        budget=budget or Budget(),
        capability="check_suites",
    )


def fetch_workflow_runs(
    repository: str,
    sha: str,
    *,
    token: str | None,
    api_url: str = DEFAULT_API_URL,
    budget: Budget | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Actions workflow runs for the exact head SHA (metadata stream)."""
    api_url = validate_api_url(api_url)
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    runs, truncated = _paginate(
        f"{api_url}/repos/{_slug(repository)}/actions/runs?head_sha={sha}",
        "workflow_runs",
        headers,
        budget=budget or Budget(),
        capability="workflow_runs",
    )
    # exact-SHA discipline: the head_sha filter is server-side, but the
    # subject binding is verified locally rather than trusted
    return [
        run for run in runs if run.get("head_sha") == sha
    ], truncated


def _suite_state(status: Any, conclusion: Any) -> str:
    """Model one execution unit's lifecycle state.

    ``action_required`` (an approval or intervention gate, e.g. a fork
    PR awaiting first-time-contributor approval) is distinguished from
    plain ``pending`` because the operator's next action differs:
    nothing will ever run until someone acts.
    """
    if conclusion == "action_required" or status in (
        "action_required", "waiting",
    ):
        return ACTION_REQUIRED
    if status == "completed":
        return COMPLETED
    return PENDING


def workflow_visibility(
    suites: list[dict[str, Any]],
    workflow_runs: list[dict[str, Any]],
    *,
    suites_truncated: bool = False,
    runs_truncated: bool = False,
) -> dict[str, Any]:
    """Join the two streams into one deduplicated visibility report.

    Keyed by check-suite id; a workflow run enriches its suite (name,
    event, attempt) and is counted exactly once even when both streams
    list it. Completed units are counted but not itemized — the report
    exists to make the *not started* set visible, at low noise.
    """
    units: dict[int, dict[str, Any]] = {}
    for suite in suites:
        suite_id = suite.get("id")
        if not isinstance(suite_id, int):
            continue
        raw_app = suite.get("app")
        app: dict[str, Any] = raw_app if isinstance(raw_app, dict) else {}
        units[suite_id] = {
            "check_suite_id": suite_id,
            "app_id": app.get("id"),
            "app_slug": app.get("slug"),
            "status": suite.get("status"),
            "conclusion": suite.get("conclusion"),
            "state": _suite_state(suite.get("status"), suite.get("conclusion")),
            "source": "check_suites",
        }
    for run in workflow_runs:
        suite_id = run.get("check_suite_id")
        if not isinstance(suite_id, int):
            continue
        unit = units.get(suite_id)
        if unit is None:
            # the suite listing missed it (truncation); count it once,
            # from the runs stream, still keyed by its suite id
            unit = {
                "check_suite_id": suite_id,
                "app_id": None,
                "app_slug": "github-actions",
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
                "state": _suite_state(
                    run.get("status"), run.get("conclusion")
                ),
                "source": "workflow_runs",
            }
            units[suite_id] = unit
        if isinstance(run.get("name"), str):
            unit["workflow_name"] = run["name"]
        if isinstance(run.get("event"), str):
            unit["event"] = run["event"]
        if isinstance(run.get("id"), int):
            unit["run_id"] = run["id"]
        # a workflow run carries lifecycle detail a suite may lack
        # (e.g. status "waiting" while the suite still says "queued")
        run_state = _suite_state(run.get("status"), run.get("conclusion"))
        if run_state == ACTION_REQUIRED:
            unit["state"] = ACTION_REQUIRED

    states = {COMPLETED: 0, PENDING: 0, ACTION_REQUIRED: 0}
    not_started: list[dict[str, Any]] = []
    for suite_id in sorted(units):
        unit = units[suite_id]
        states[unit["state"]] = states.get(unit["state"], 0) + 1
        if unit["state"] != COMPLETED:
            not_started.append(unit)

    report: dict[str, Any] = {
        "available": True,
        "units_total": len(units),
        "states": states,
        "not_started": not_started,
    }
    if suites_truncated or runs_truncated:
        report["truncated"] = True
    return report


def collect_workflow_visibility(
    repository: str,
    sha: str,
    *,
    token: str | None,
    api_url: str = DEFAULT_API_URL,
    budget: Budget | None = None,
) -> dict[str, Any]:
    """Fetch both streams and build the report; degrade, never abort.

    Visibility is non-essential evidence: an unreadable stream yields
    ``{"available": false, "unavailable": <reason>}`` (can_continue:
    yes) so the gate still decides — the absence of visibility is
    itself recorded instead of silently dropped.
    """
    budget = budget or Budget()
    try:
        suites, suites_truncated = fetch_check_suites(
            repository, sha, token=token, api_url=api_url, budget=budget
        )
    except InputError as exc:
        return {"available": False, "unavailable": str(exc)}
    try:
        runs, runs_truncated = fetch_workflow_runs(
            repository, sha, token=token, api_url=api_url, budget=budget
        )
    except InputError as exc:
        # the suites alone still describe the commit; the runs stream's
        # absence is disclosed on the report it would have enriched
        report = workflow_visibility(
            suites, [], suites_truncated=suites_truncated
        )
        report["workflow_runs_unavailable"] = str(exc)
        return report
    return workflow_visibility(
        suites,
        runs,
        suites_truncated=suites_truncated,
        runs_truncated=runs_truncated,
    )
