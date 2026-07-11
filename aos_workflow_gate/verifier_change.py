"""Trusted verifier-change awareness: self-validating changes are named.

Version 0 makes one deliberately narrow determination: when a pull
request changes a GitHub Actions workflow definition and a run of that
exact workflow produces checks for the same head SHA, those checks are
not independent evidence. Other verifier-adjacent paths are recorded,
but no dependency relationship is inferred from paths alone.

Every determination here is a pure function of observed facts: changed
file paths, workflow-run paths, and check-suite identifiers. **No model
output participates in any verdict path**, and nothing is executed.

An unchanged workflow run is recorded only as a possible alternative;
its governance and transitive dependencies are not proven here. An
operator acknowledgement is also evidence, never authorization, and
never suppresses a policy reason.

Routine dependency bumps are excluded mechanically (bot author, only
dependency-pin or packaging-metadata files, no workflow/scanner
surface) and the exclusion is recorded, never silent.
"""

from __future__ import annotations

import re
from typing import Any

from .collect import Budget, _request_json
from .errors import InputError

WORKFLOW_RE = re.compile(r"^\.github/workflows/[^/]+\.(yml|yaml)$")
TEST_HARNESS_RE = re.compile(
    r"(^|/)conftest\.py$|(^|/)(tox|noxfile|pytest)\.(ini|py|toml)$"
)
TEST_CASE_RE = re.compile(r"(^|/)(tests?|testing)/")
SCANNER_CONFIG_RE = re.compile(
    r"(^|/)(\.pre-commit-config\.ya?ml|codecov\.ya?ml|\.codecov\.ya?ml|"
    r"sonar-project\.properties|\.github/dependabot\.ya?ml|"
    r"\.golangci\.ya?ml|\.eslintrc[^/]*|ruff\.toml|\.ruff\.toml|mypy\.ini)$"
)
POLICY_RE = re.compile(r"(^|/)policies/[^/]+\.(ya?ml|json)$")
PACKAGING_RE = re.compile(r"(^|/)(pyproject\.toml|setup\.cfg|setup\.py)$")
DEPENDENCY_PIN_RE = re.compile(
    r"(^|/)(requirements[^/]*\.txt|poetry\.lock|Pipfile\.lock|"
    r"package-lock\.json|yarn\.lock|pnpm-lock\.ya?ml|go\.sum|Cargo\.lock|"
    r"constraints[^/]*\.txt)$"
)
_PER_PAGE = 100
_MAX_PR_FILE_PAGES = 30


def classify_verifier_paths(
    paths: list[str], *, extra_policy_paths: list[str] | None = None
) -> dict[str, list[str]]:
    """Split changed paths into verifier surfaces (everything is kept).

    ``extra_policy_paths`` names operator-supplied policy files (the
    ``--policy`` argument) that live outside the conventional
    ``policies/`` directory.
    """
    extra = set(extra_policy_paths or [])
    buckets: dict[str, list[str]] = {
        "workflow": [], "test_harness": [], "test_cases": [],
        "scanner_config": [],
        "policy": [], "dependency_pins": [], "packaging": [], "other": [],
    }
    for path in paths:
        if WORKFLOW_RE.match(path):
            buckets["workflow"].append(path)
        elif POLICY_RE.search(path) or path in extra:
            buckets["policy"].append(path)
        elif SCANNER_CONFIG_RE.search(path):
            buckets["scanner_config"].append(path)
        elif TEST_HARNESS_RE.search(path):
            buckets["test_harness"].append(path)
        elif TEST_CASE_RE.search(path):
            buckets["test_cases"].append(path)
        elif DEPENDENCY_PIN_RE.search(path):
            buckets["dependency_pins"].append(path)
        elif PACKAGING_RE.search(path):
            buckets["packaging"].append(path)
        else:
            buckets["other"].append(path)
    return {key: sorted(value) for key, value in buckets.items()}


def is_routine_bump(buckets: dict[str, list[str]], *, bot_author: bool) -> bool:
    """Mechanical routine-bump exclusion (recorded, never silent).

    A bot-authored change touching only dependency pins and packaging
    metadata is a version bump, not a verifier rewrite: packaging
    metadata is formally part of the harness surface, but a pin-only
    delta cannot change what the harness verifies.
    """
    if not bot_author:
        return False
    verifier_surface = (
        buckets["workflow"] or buckets["scanner_config"]
        or buckets["policy"] or buckets["test_harness"]
        or buckets["test_cases"]
    )
    only_bump_files = not buckets["other"] and (
        buckets["dependency_pins"] or buckets["packaging"]
    )
    return bool(not verifier_surface and only_bump_files)


def fetch_pr_files(
    api_url: str,
    slug: str,
    number: int,
    *,
    token: str | None,
    budget: Budget,
) -> tuple[list[str], bool]:
    """Return changed paths and whether GitHub's file cap was reached.

    Renames include both the current and previous path. GitHub documents
    a 3,000-file response ceiling, so a full final page is explicitly
    truncated rather than treated as complete.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    paths: list[str] = []
    for page in range(1, _MAX_PR_FILE_PAGES + 1):
        payload = _request_json(
            f"{api_url}/repos/{slug}/pulls/{number}/files"
            f"?per_page=100&page={page}",
            headers,
            timeout=30.0,
            budget=budget,
            capability="pull_request",
        )
        if not isinstance(payload, list):
            raise InputError("pull request files response is not a list")
        for item in payload:
            if not isinstance(item, dict):
                continue
            for key in ("filename", "previous_filename"):
                value = item.get(key)
                if isinstance(value, str) and value:
                    paths.append(value)
        if len(payload) < _PER_PAGE:
            return sorted(set(paths)), False
    return sorted(set(paths)), True


def _suite_id(run: dict[str, Any]) -> int | None:
    suite = run.get("check_suite")
    if isinstance(suite, dict) and isinstance(suite.get("id"), int):
        return suite["id"]
    value = run.get("check_suite_id")
    return value if isinstance(value, int) else None


def analyze_verifier_change(
    changed_paths: list[str],
    workflow_runs: list[dict[str, Any]],
    check_runs: list[dict[str, Any]],
    *,
    bot_author: bool = False,
    acknowledged: str | None = None,
    extra_policy_paths: list[str] | None = None,
) -> dict[str, Any]:
    """Pure, model-free analysis of one change against its evidence.

    ``workflow_runs`` are the head SHA's Actions runs (with ``path`` and
    ``check_suite_id``); ``check_runs`` are the raw collected check runs
    (with ``name`` and ``check_suite.id``). Returns the evidence object
    committed into the bundle's collection.
    """
    buckets = classify_verifier_paths(
        changed_paths, extra_policy_paths=extra_policy_paths
    )
    # Only workflow definitions can be joined mechanically to workflow runs.
    verifier_changed = bool(buckets["workflow"])
    routine_bump = is_routine_bump(buckets, bot_author=bot_author)

    changed_workflow_paths = set(buckets["workflow"])
    self_validating_runs = [
        run for run in workflow_runs
        if isinstance(run.get("path"), str)
        and run["path"] in changed_workflow_paths
    ]
    unchanged_runs = [
        run for run in workflow_runs
        if isinstance(run.get("path"), str)
        and run["path"] not in changed_workflow_paths
    ]
    non_independent_suites = sorted(
        {
            suite
            for run in self_validating_runs
            if (suite := _suite_id(run)) is not None
        }
    )
    suite_set = set(non_independent_suites)
    non_independent_sources = sorted(
        {
            str(run.get("name"))
            for run in check_runs
            if isinstance(run.get("name"), str)
            and _suite_id(run) in suite_set
        }
    )

    evidence: dict[str, Any] = {
        "analyzed": True,
        "verifier_change": verifier_changed,
        "changed": {
            "workflow": buckets["workflow"],
            "test_harness": buckets["test_harness"],
            "test_cases": buckets["test_cases"],
            "scanner_config": buckets["scanner_config"],
            "policy": buckets["policy"],
        },
        "routine_bump_excluded": routine_bump,
        "self_validating_workflows": sorted(
            {str(run.get("path")) for run in self_validating_runs}
        ),
        "non_independent_suites": non_independent_suites,
        "non_independent_sources": non_independent_sources,
        "unchanged_workflow_runs": len(unchanged_runs),
        "scope": "changed_workflow_definitions_v0",
        "note": (
            "mechanical determination from changed paths, workflow-run "
            "paths, and check-suite ids; no model output participates "
            "in any verdict path"
        ),
    }
    if acknowledged:
        evidence["acknowledged"] = acknowledged
    return evidence
