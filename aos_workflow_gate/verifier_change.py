"""Trusted verifier-change awareness: self-validating changes are named.

When a pull request changes its own verification mechanism — a workflow
file, the test harness, policy files, or scanner configuration —
evidence generated **solely by the changed mechanism** must not be
treated as independent: the change grades itself with the grader it
just edited. This module detects that condition mechanically and
records it as evidence; the policy decides what it means (advisory WARN
by default, raisable to BLOCK, or explicitly approved).

Every determination here is a pure function of observed facts: changed
file paths, workflow-run paths, and check-suite identifiers. **No model
output participates in any verdict path**, and nothing is executed.

What restores trust, mechanically:

- a *trusted verifier*: a workflow whose definition file the change did
  not touch (it runs the protected ref's logic, or at least logic this
  change cannot have rewritten), observed as a workflow run whose
  ``path`` is not among the changed workflow files; or
- *explicit approval*: an operator-recorded acceptance
  (``--accept-verifier-change``), which suppresses the reason but is
  itself committed into the bundle as evidence.

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
    r"(^|/)(tests?|testing)/|(^|/)conftest\.py$|(^|/)(tox|noxfile|pytest)"
    r"\.(ini|py|toml)$"
)
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
        "workflow": [], "test_harness": [], "scanner_config": [],
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
) -> list[str]:
    """Changed file paths of a pull request (paginated)."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    paths: list[str] = []
    for page in range(1, 4):
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
        page_paths = [
            str(item.get("filename"))
            for item in payload
            if isinstance(item, dict) and item.get("filename")
        ]
        paths.extend(page_paths)
        if len(payload) < 100:
            break
    return paths


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
    approved: str | None = None,
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
    verifier_changed = bool(
        buckets["workflow"] or buckets["test_harness"]
        or buckets["scanner_config"] or buckets["policy"]
    )
    routine_bump = is_routine_bump(buckets, bot_author=bot_author)

    changed_workflow_paths = set(buckets["workflow"])
    self_validating_runs = [
        run for run in workflow_runs
        if isinstance(run.get("path"), str)
        and run["path"] in changed_workflow_paths
    ]
    trusted_runs = [
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
            "scanner_config": buckets["scanner_config"],
            "policy": buckets["policy"],
        },
        "routine_bump_excluded": routine_bump,
        "self_validating_workflows": sorted(
            {str(run.get("path")) for run in self_validating_runs}
        ),
        "non_independent_suites": non_independent_suites,
        "non_independent_sources": non_independent_sources,
        "trusted_verifier_runs": len(trusted_runs),
        "note": (
            "mechanical determination from changed paths, workflow-run "
            "paths, and check-suite ids; no model output participates "
            "in any verdict path"
        ),
    }
    if approved:
        evidence["approved"] = approved
    return evidence
