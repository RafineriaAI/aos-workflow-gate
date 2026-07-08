"""Instant merge-protection check for a GitHub pull request URL.

``check-pr`` is a read-only observer: it fetches the PR head, the ACTIVE
branch rules of the base branch, and the head's check runs, then evaluates
a policy generated from the rules' required status checks. The verdict
reports what the rules enforce and what actually ran — it does not gate
the merge button itself, and it makes no safety judgment.

Canonical control identity: a required check's identity is its status
context plus the enforcing integration id when the rules declare one; both
are committed into the policy source metadata and the rules digest, so the
same control keeps the same identity across runs, time, and mirrors.

Temporal drift primitive: the bundle carries ``rules_digest`` — two
``check-pr`` records for the same branch differ in ``rules_digest`` exactly
when the protection rules changed between them.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from . import canonical
from .collect import Budget, _request_json, validate_api_url
from .errors import InputError

_PR_PATH = re.compile(r"^/([^/]+)/([^/]+)/pull/(\d+)(?:/.*)?$")


def parse_pr_url(url: str) -> dict[str, Any]:
    """Parse a GitHub / GHES pull request URL into API coordinates."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise InputError(f"not a https pull request URL: {url!r}")
    match = _PR_PATH.match(parsed.path or "")
    if not match:
        raise InputError(
            f"not a pull request URL (expected .../OWNER/REPO/pull/N): {url!r}"
        )
    owner, repo, number = match.group(1), match.group(2), int(match.group(3))
    host = parsed.hostname
    if host in ("github.com", "www.github.com"):
        api_url = "https://api.github.com"
        repository = f"{owner}/{repo}"
    else:
        api_url = f"https://{host}/api/v3"
        repository = f"https://{host}/{owner}/{repo}"
    return {
        "api_url": validate_api_url(api_url),
        "slug": f"{owner}/{repo}",
        "repository": repository,
        "number": number,
    }


def fetch_pr(
    api_url: str, slug: str, number: int, *, token: str | None, budget: Budget
) -> dict[str, Any]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = _request_json(
        f"{api_url}/repos/{slug}/pulls/{number}",
        headers,
        timeout=30.0,
        budget=budget,
    )
    if not isinstance(payload, dict):
        raise InputError("pull request API response is not a JSON object")
    head = payload.get("head") or {}
    base = payload.get("base") or {}
    sha = head.get("sha")
    base_ref = base.get("ref")
    if not isinstance(sha, str) or not isinstance(base_ref, str):
        raise InputError("pull request API response has no head sha/base ref")
    head_repo = (head.get("repo") or {}).get("full_name")
    base_repo = (base.get("repo") or {}).get("full_name")
    return {
        "head_sha": sha,
        "base_ref": base_ref,
        "state": payload.get("state"),
        "merged": bool(payload.get("merged")),
        "draft": bool(payload.get("draft")),
        "from_fork": bool(head_repo and base_repo and head_repo != base_repo),
    }


def fetch_commit_statuses(
    api_url: str, slug: str, sha: str, *, token: str | None, budget: Budget
) -> list[dict[str, Any]]:
    """Fetch legacy commit statuses (Status API) for a commit.

    Required status checks can be satisfied by legacy statuses, not only
    check runs; ignoring them would fail-closed a context that GitHub
    itself considers green.
    """
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = _request_json(
        f"{api_url}/repos/{slug}/commits/{sha}/status",
        headers,
        timeout=30.0,
        budget=budget,
    )
    if not isinstance(payload, dict):
        raise InputError("commit status API response is not a JSON object")
    statuses = payload.get("statuses")
    return [s for s in statuses if isinstance(s, dict)] if isinstance(
        statuses, list
    ) else []


_STATUS_STATE_MAP = {"success": "success", "failure": "failure",
                     "error": "failure", "pending": "pending"}


def status_sources(
    statuses: list[dict[str, Any]], *, exclude_contexts: set[str]
) -> tuple[list[dict[str, Any]], list[str]]:
    """Reduce legacy statuses to sources; check-run names take precedence.

    Returns the sources plus the contexts skipped because a check run with
    the same name already exists (GitHub shares one context namespace).
    """
    sources: list[dict[str, Any]] = []
    skipped: list[str] = []
    seen: set[str] = set()
    for status in statuses:
        context = status.get("context")
        if not isinstance(context, str) or not context or context in seen:
            continue
        seen.add(context)
        if context in exclude_contexts:
            skipped.append(context)
            continue
        raw_state = str(status.get("state", "unknown")).lower()
        state = _STATUS_STATE_MAP.get(raw_state, raw_state)
        identity = {"context": context, "state": raw_state}
        sources.append(
            {
                "id": context,
                "kind": "commit_status",
                "signal_source": "github_status_api",
                "status": state,
                "required": False,
                "summary": f"Legacy commit status '{context}' is {raw_state}.",
                "digest": canonical.digest(identity),
            }
        )
    return sources, sorted(skipped)


def fetch_branch_rules(
    api_url: str, slug: str, branch: str, *, token: str | None, budget: Budget
) -> list[dict[str, Any]]:
    """Fetch the ACTIVE aggregated rules for a branch (rulesets included)."""
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    url = f"{api_url}/repos/{slug}/rules/branches/{branch}"
    payload = _request_json(url, headers, timeout=30.0, budget=budget)
    rules = payload if isinstance(payload, list) else payload.get("rules")
    if not isinstance(rules, list):
        return []
    return [rule for rule in rules if isinstance(rule, dict)]


def required_checks_from_rules(
    rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Extract canonical control identities of required status checks."""
    controls: dict[str, dict[str, Any]] = {}
    for rule in rules:
        if rule.get("type") != "required_status_checks":
            continue
        params = rule.get("parameters") or {}
        for check in params.get("required_status_checks") or []:
            if not isinstance(check, dict):
                continue
            context = check.get("context")
            if not isinstance(context, str) or not context:
                continue
            controls[context] = {
                "context": context,
                "integration_id": check.get("integration_id"),
            }
    return [controls[key] for key in sorted(controls)]


def strict_policy_from_rules(rules: list[dict[str, Any]]) -> bool:
    """Whether the rules require the branch to be up to date (strict).

    The gate's verdict is head-SHA-scoped; when strict is on, GitHub
    additionally requires the branch to be current — surfaced so the
    record cannot be over-read.
    """
    for rule in rules:
        if rule.get("type") != "required_status_checks":
            continue
        params = rule.get("parameters") or {}
        if bool(params.get("strict_required_status_checks_policy")):
            return True
    return False


def rules_digest(rules: list[dict[str, Any]]) -> str:
    """Canonical digest of the protection surface (drift primitive)."""
    identity = {
        "rule_types": sorted(
            str(rule.get("type")) for rule in rules if rule.get("type")
        ),
        "required_status_checks": required_checks_from_rules(rules),
        "strict": strict_policy_from_rules(rules),
    }
    return canonical.digest(identity)


def rules_summary_source(rules: list[dict[str, Any]]) -> dict[str, Any]:
    """The branch-protection surface as a mechanical source."""
    types: dict[str, int] = {}
    for rule in rules:
        name = str(rule.get("type", "unknown"))
        types[name] = types.get(name, 0) + 1
    required = required_checks_from_rules(rules)
    summary_types = ", ".join(f"{k}x{v}" for k, v in sorted(types.items()))
    return {
        "id": "branch.rules",
        "kind": "branch_rules_summary",
        "signal_source": "github_rules_api",
        "status": "success",
        "required": False,
        "summary": (
            f"Active branch rules: {summary_types or 'none'}; "
            f"{len(required)} required status check(s)."
        ),
        "digest": rules_digest(rules),
    }


def pending_required(
    raw_runs: list[dict[str, Any]],
    status_srcs: list[dict[str, Any]],
    required_ids: list[str],
) -> list[str]:
    """Required contexts that exist but have not finished.

    Distinguishes "still running" from "absent": both fail closed to
    BLOCK, but the record and the operator hint should not conflate them.
    """
    required = set(required_ids)
    pending: set[str] = set()
    for run in raw_runs:
        name = run.get("name")
        if (
            isinstance(name, str)
            and name in required
            and run.get("status") != "completed"
        ):
            pending.add(name)
    for source in status_srcs:
        if source.get("id") in required and source.get("status") == "pending":
            pending.add(str(source.get("id")))
    return sorted(pending)


def counterfactual_blockers(
    sources: list[dict[str, Any]],
) -> list[str]:
    """Deterministic counterfactual: non-required, non-success check runs
    that would make the verdict BLOCK if they were required."""
    return sorted(
        str(source.get("id"))
        for source in sources
        if isinstance(source, dict)
        and source.get("kind") in ("github_check", "commit_status")
        and not source.get("required")
        and str(source.get("status", "")).lower() != "success"
    )
