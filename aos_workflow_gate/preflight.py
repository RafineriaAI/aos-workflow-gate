"""Read-only preflight diagnostics for gate capabilities.

``preflight`` probes what the current token, environment, and target
actually allow — repository metadata, pull request access, check runs,
commit statuses, and active branch rules — and reports stable diagnostic
codes with remediation. Nothing is assumed about token permissions:
every capability is probed empirically and classified from the observed
HTTP behavior, because permission models differ between the workflow
``GITHUB_TOKEN``, fine-grained tokens, classic tokens, and GHES versions.

The output is a diagnostic readiness report, never a policy verdict:
exit 0 means every probed capability responded, exit 1 means at least
one probed capability is unavailable (each one is named with a stable
code), exit 2 means the probe run itself could not complete.

Diagnostic codes are stable: a code never changes meaning across
versions. The registry lives in docs/PREFLIGHT.md.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote

from .checkpr import parse_pr_url, required_checks_from_rules
from .collect import (
    API_TIMEOUT_SECONDS,
    DEFAULT_API_URL,
    Budget,
    github_context_snapshot,
    resolve_github_context,
    validate_api_url,
)
from .errors import InputError
from .paths import WORKSPACE_ENV
from .version import __version__

REPORT_SCHEMA_VERSION = "preflight-report-v0"
LOW_RATE_LIMIT_REMAINING = 20

_TAXONOMY = {
    "ENV": "environment",
    "PERM": "permission",
    "FEAT": "feature",
    "CTX": "context",
}

_SEVERITY_ORDER = {"error": 0, "warn": 1, "info": 2}

# Likely causes shown as remediation for an observed HTTP 403. These are
# suggestions derived from common token models, not assumptions the probe
# relies on: the classification itself comes only from the response.
_FORBIDDEN_HINTS = {
    "check_runs": (
        "the token cannot read check runs; a workflow `permissions:` "
        "block commonly needs `checks: read`, a fine-grained token needs "
        "Checks read access — verify against your token type"
    ),
    "commit_statuses": (
        "the token cannot read commit statuses; contents/commit read "
        "access is commonly required — verify against your token type"
    ),
    "branch_rules": (
        "the token cannot read branch rules; repository metadata read "
        "access is commonly required — verify against your token type"
    ),
    "pull_request": (
        "the token cannot read this pull request; pull request read "
        "access is commonly required — verify against your token type"
    ),
    "repository": (
        "the token cannot read this repository; repository read access "
        "is commonly required — verify against your token type"
    ),
}


def _finding(
    code: str,
    capability: str,
    observed: str,
    remediation: str,
    severity: str,
) -> dict[str, Any]:
    prefix = code.split("-")[1]
    return {
        "code": code,
        "taxonomy": _TAXONOMY[prefix],
        "severity": severity,
        "capability": capability,
        "observed": observed,
        "remediation": remediation,
    }


def classify_response(
    capability: str, http_status: int, *, rate_limited: bool
) -> dict[str, Any] | None:
    """Classify a probe's HTTP response into a finding, if any.

    Only the observed response is used — no permission model is assumed.
    2xx responses produce no finding here; feature-level observations
    (a capability that works but is unused) are added by the caller.
    """
    if 200 <= http_status < 300:
        return None
    if http_status == 401:
        return _finding(
            "AOS-PERM-001",
            capability,
            f"HTTP 401 while probing {capability}",
            "the API rejected the credentials; the token is invalid, "
            "expired, or malformed — replace it and re-run preflight",
            "error",
        )
    if rate_limited:
        return _finding(
            "AOS-PERM-004",
            capability,
            f"HTTP {http_status} rate-limited while probing {capability}",
            "the rate limit is exhausted, so capability cannot be "
            "determined now; wait for the limit window to reset, or "
            "authenticate to get a higher limit",
            "error",
        )
    if http_status == 403:
        return _finding(
            "AOS-PERM-002",
            capability,
            f"HTTP 403 while probing {capability}",
            _FORBIDDEN_HINTS.get(
                capability,
                "the API denied access to this capability — verify the "
                "token's access against your token type",
            ),
            "error",
        )
    if http_status == 404:
        return _finding(
            "AOS-PERM-003",
            capability,
            f"HTTP 404 while probing {capability}",
            "the resource does not exist, or it exists but the token "
            "cannot see it (the API reports both identically); check "
            "the target spelling first, then the token's repository "
            "access",
            "error",
        )
    return _finding(
        "AOS-ENV-002",
        capability,
        f"HTTP {http_status} while probing {capability}",
        "unexpected API response; if it persists, the endpoint may be "
        "unavailable on this server version",
        "error",
    )


def _probe_get(
    url: str,
    headers: dict[str, str],
    *,
    budget: Budget,
    timeout: float = API_TIMEOUT_SECONDS,
) -> tuple[int, Any, bool, str | None]:
    """One diagnostic GET: (http_status, payload, rate_limited, error).

    A single attempt, deliberately without retries — preflight reports
    what the environment does right now. ``http_status`` 0 means the
    request never reached the API (network failure); ``error`` then
    carries the cause.
    """
    budget.take_call()
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            try:
                payload = json.load(response)
            except (json.JSONDecodeError, ValueError):
                payload = None
            status = getattr(response, "status", None)
            return (status if isinstance(status, int) else 200), payload, False, None
    except HTTPError as exc:
        rate_limited = exc.code == 429 or (
            exc.code == 403
            and exc.headers is not None
            and (
                exc.headers.get("X-RateLimit-Remaining") == "0"
                or bool(exc.headers.get("Retry-After"))
            )
        )
        return exc.code, None, rate_limited, None
    except (URLError, OSError) as exc:
        return 0, None, False, str(exc)


def _slug_of(repository: str) -> str:
    parts = repository.rstrip("/").rsplit("/", 2)
    return "/".join(parts[-2:]) if len(parts) >= 2 else repository


def run_preflight(
    *,
    pr_url: str | None = None,
    repository: str | None = None,
    sha: str | None = None,
    branch: str | None = None,
    github_context: bool = False,
    token: str | None = None,
    api_url: str | None = None,
    budget: Budget | None = None,
) -> dict[str, Any]:
    """Probe the environment and target; return the readiness report.

    Probes run in dependency order; when a prerequisite fails (network
    unreachable, credentials rejected, repository unavailable) the
    dependent probes are recorded as skipped instead of repeating the
    same failure five times.
    """
    budget = budget or Budget()
    probes: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []

    def probe(capability: str, endpoint: str, status: str, **observed: Any) -> None:
        probes.append(
            {
                "capability": capability,
                "endpoint": endpoint,
                "status": status,
                "observed": dict(observed),
            }
        )

    # -- runtime and context (no network) --------------------------------
    probe(
        "runtime",
        "(local)",
        "available",
        python=".".join(str(part) for part in sys.version_info[:3]),
    )

    workspace_raw = os.environ.get(WORKSPACE_ENV)
    if workspace_raw and workspace_raw.strip():
        if os.path.isdir(workspace_raw):
            probe("workspace", "(local)", "available", path_configured=True)
        else:
            probe("workspace", "(local)", "unavailable", path_configured=True)
            findings.append(
                _finding(
                    "AOS-ENV-003",
                    "workspace",
                    f"{WORKSPACE_ENV} is set but is not an existing "
                    "directory",
                    "point the variable at the job workspace directory, "
                    "or unset it for unbounded local output paths",
                    "error",
                )
            )
    else:
        probe("workspace", "(local)", "skipped", path_configured=False)

    pull_number: int | None = None
    slug: str | None = None
    resolved_api: str | None = None

    if pr_url:
        coords = parse_pr_url(pr_url)
        slug = coords["slug"]
        resolved_api = coords["api_url"]
        pull_number = coords["number"]
    elif repository:
        slug = _slug_of(repository)
        if "/" not in slug:
            raise InputError(
                f"--repository must be owner/repo, got {repository!r}"
            )
    elif github_context:
        if os.environ.get("GITHUB_ACTIONS") != "true":
            findings.append(
                _finding(
                    "AOS-CTX-002",
                    "actions_context",
                    "GITHUB_ACTIONS is not 'true'; this is not a GitHub "
                    "Actions runtime",
                    "run with --pr or --repository outside workflows; "
                    "--github-context is for workflow-scoped probing",
                    "info",
                )
            )
        try:
            context = resolve_github_context()
            slug = _slug_of(str(context["repository"]))
            sha = sha or (
                context["sha"] if isinstance(context["sha"], str) else None
            )
            probe(
                "actions_context",
                "(env)",
                "available",
                snapshot_keys=sorted(github_context_snapshot()),
            )
        except InputError as exc:
            probe("actions_context", "(env)", "unavailable")
            findings.append(
                _finding(
                    "AOS-CTX-001",
                    "actions_context",
                    f"GitHub Actions context incomplete: {exc}",
                    "the identity variables GitHub Actions sets "
                    "(GITHUB_REPOSITORY, GITHUB_SHA) are missing or "
                    "unusable; do not unset them in workflow steps",
                    "error",
                )
            )
    else:
        raise InputError(
            "preflight needs --pr, --repository, or --github-context"
        )

    if token is None:
        findings.append(
            _finding(
                "AOS-ENV-001",
                "credentials",
                "no API token available; probing anonymously",
                "anonymous probing works for public repositories at a "
                "low rate limit; set the token env var (default "
                "GITHUB_TOKEN) to probe what your real credentials can "
                "do",
                "info",
            )
        )

    report: dict[str, Any] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generator": {"name": "aos-workflow-gate", "version": __version__},
        "scope": "workflow" if github_context else "operator",
        "target": {
            "repository": slug,
            "pull_request": pull_number,
            "sha": sha,
            "branch": branch,
        },
        "token_present": token is not None,
        "boundary": (
            "diagnostic readiness report: it states which capabilities "
            "responded to read-only probes, nothing about code quality, "
            "security, or any policy outcome"
        ),
    }

    if slug is None:
        report.update(
            {"api_url": None, "probes": probes, "findings": findings}
        )
        report["ready"] = not _has_errors(findings)
        return report

    resolved_api = validate_api_url(
        resolved_api
        or api_url
        or os.environ.get("GITHUB_API_URL")
        or DEFAULT_API_URL
    )
    report["api_url"] = resolved_api
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # -- network probes, dependency-ordered ------------------------------
    halt_reason: str | None = None

    def network_probe(
        capability: str, path: str
    ) -> tuple[int, Any] | None:
        nonlocal halt_reason
        if halt_reason:
            probe(capability, path, "skipped", skipped_reason=halt_reason)
            return None
        code, payload, rate_limited, error = _probe_get(
            f"{resolved_api}{path}", headers, budget=budget
        )
        if error is not None:
            probe(capability, path, "unavailable", network_error=error)
            findings.append(
                _finding(
                    "AOS-ENV-002",
                    capability,
                    f"API unreachable while probing {capability}: {error}",
                    "the API endpoint could not be reached at all; check "
                    "network egress, proxy configuration, and the "
                    "--api-url value",
                    "error",
                )
            )
            halt_reason = "API unreachable"
            return None
        finding = classify_response(
            capability, code, rate_limited=rate_limited
        )
        if finding is not None:
            probe(capability, path, "unavailable", http_status=code)
            findings.append(finding)
            if finding["code"] in ("AOS-PERM-001", "AOS-PERM-004"):
                halt_reason = (
                    "credentials rejected"
                    if finding["code"] == "AOS-PERM-001"
                    else "rate limited"
                )
            return None
        probe(capability, path, "available", http_status=code)
        return code, payload

    rate = network_probe("rate_limit", "/rate_limit")
    if rate is not None:
        _, payload = rate
        remaining = None
        if isinstance(payload, dict):
            core = (payload.get("resources") or {}).get("core") or {}
            remaining = core.get("remaining")
        if isinstance(remaining, int):
            probes[-1]["observed"]["rate_limit_remaining"] = remaining
            if remaining < LOW_RATE_LIMIT_REMAINING:
                findings.append(
                    _finding(
                        "AOS-ENV-004",
                        "rate_limit",
                        f"only {remaining} API requests remain in the "
                        "current rate-limit window",
                        "collection may exhaust the window mid-run; wait "
                        "for the reset, or authenticate for a higher "
                        "limit",
                        "warn",
                    )
                )

    default_branch: str | None = None
    repo = network_probe("repository", f"/repos/{slug}")
    if repo is not None:
        _, payload = repo
        if isinstance(payload, dict):
            value = payload.get("default_branch")
            default_branch = value if isinstance(value, str) else None
            probes[-1]["observed"]["private"] = bool(payload.get("private"))
    elif halt_reason is None:
        halt_reason = "repository unavailable"

    if pull_number is not None:
        pull = network_probe(
            "pull_request", f"/repos/{slug}/pulls/{pull_number}"
        )
        if pull is not None:
            _, payload = pull
            if isinstance(payload, dict):
                head = payload.get("head") or {}
                base = payload.get("base") or {}
                head_sha = head.get("sha")
                base_ref = base.get("ref")
                if sha is None and isinstance(head_sha, str):
                    sha = head_sha
                if branch is None and isinstance(base_ref, str):
                    branch = base_ref

    ref = sha or default_branch
    if ref is None:
        probe(
            "check_runs",
            f"/repos/{slug}/commits/{{ref}}/check-runs",
            "skipped",
            skipped_reason="no commit or default branch resolved",
        )
        probe(
            "commit_statuses",
            f"/repos/{slug}/commits/{{ref}}/status",
            "skipped",
            skipped_reason="no commit or default branch resolved",
        )
    else:
        quoted_ref = quote(ref, safe="")
        checks = network_probe(
            "check_runs",
            f"/repos/{slug}/commits/{quoted_ref}/check-runs?per_page=1",
        )
        if checks is not None:
            _, payload = checks
            total = (
                payload.get("total_count")
                if isinstance(payload, dict)
                else None
            )
            if isinstance(total, int):
                probes[-1]["observed"]["check_runs_total"] = total
                if total == 0:
                    findings.append(
                        _finding(
                            "AOS-FEAT-001",
                            "check_runs",
                            "the Checks API is readable but reports zero "
                            "check runs for the probed commit",
                            "if check runs were expected, confirm CI ran "
                            "for this commit; CI systems using the legacy "
                            "Status API report under commit statuses "
                            "instead",
                            "info",
                        )
                    )
        statuses = network_probe(
            "commit_statuses", f"/repos/{slug}/commits/{quoted_ref}/status"
        )
        if statuses is not None:
            _, payload = statuses
            listed = (
                payload.get("statuses") if isinstance(payload, dict) else None
            )
            if isinstance(listed, list):
                probes[-1]["observed"]["statuses_total"] = len(listed)
                if not listed:
                    findings.append(
                        _finding(
                            "AOS-FEAT-003",
                            "commit_statuses",
                            "no legacy commit statuses on the probed "
                            "commit",
                            "informational only; CI reporting through "
                            "check runs does not use the legacy Status "
                            "API",
                            "info",
                        )
                    )

    rules_branch = branch or default_branch
    if rules_branch is None:
        probe(
            "branch_rules",
            f"/repos/{slug}/rules/branches/{{branch}}",
            "skipped",
            skipped_reason="no branch resolved",
        )
    else:
        quoted_branch = quote(rules_branch, safe="")
        rules_result = network_probe(
            "branch_rules", f"/repos/{slug}/rules/branches/{quoted_branch}"
        )
        if rules_result is not None:
            _, payload = rules_result
            rules = payload if isinstance(payload, list) else []
            rules = [rule for rule in rules if isinstance(rule, dict)]
            required = required_checks_from_rules(rules)
            probes[-1]["observed"]["active_rules"] = len(rules)
            probes[-1]["observed"]["required_status_checks"] = len(required)
            report["target"]["branch"] = rules_branch
            if not required:
                findings.append(
                    _finding(
                        "AOS-FEAT-002",
                        "branch_rules",
                        f"no required status checks are active on "
                        f"'{rules_branch}'",
                        "no check outcome is enforced on this branch by "
                        "rules; if enforcement is intended, add required "
                        "status checks to a branch ruleset",
                        "info",
                    )
                )

    report["target"]["sha"] = sha
    report["api_calls"] = budget.api_calls
    report["probes"] = probes
    report["findings"] = sorted(
        findings, key=lambda f: (_SEVERITY_ORDER[f["severity"]], f["code"])
    )
    report["ready"] = not _has_errors(findings)
    return report


def _has_errors(findings: list[dict[str, Any]]) -> bool:
    return any(f["severity"] == "error" for f in findings)


def render_report(report: dict[str, Any], *, verbose: bool = False) -> str:
    """Human-readable rendering with progressive disclosure.

    The default view is the summary line plus findings only; ``verbose``
    adds one line per probe. Verdict words are deliberately absent — this
    report never carries a policy decision.
    """
    probes = report.get("probes", [])
    findings = report.get("findings", [])
    probed = [p for p in probes if p["status"] != "skipped"]
    unavailable = [p for p in probed if p["status"] == "unavailable"]
    lines = [
        "preflight: "
        + ("ready" if report.get("ready") else "degraded")
        + f" — {len(unavailable)} of {len(probed)} probed capabilities "
        "unavailable"
    ]
    target = report.get("target") or {}
    parts = [str(target.get("repository") or "(no repository)")]
    if target.get("pull_request") is not None:
        parts.append(f"pull {target['pull_request']}")
    if target.get("sha"):
        parts.append(f"commit {str(target['sha'])[:12]}")
    lines.append(f"target: {' '.join(parts)}  [scope: {report.get('scope')}]")
    if report.get("api_url"):
        lines.append(f"api: {report['api_url']}")
    if findings:
        lines.append("")
    for finding in findings:
        lines.append(
            f"{finding['code']} [{finding['taxonomy']}] "
            f"{finding['capability']}: {finding['observed']}"
        )
        lines.append(f"  remediation: {finding['remediation']}")
    if verbose and probes:
        lines.append("")
        lines.append("probes:")
        for entry in probes:
            observed = entry.get("observed") or {}
            detail = ", ".join(f"{k}={v}" for k, v in sorted(observed.items()))
            lines.append(
                f"  {entry['capability']}: {entry['status']}"
                + (f" ({detail})" if detail else "")
            )
    lines.append("")
    lines.append(
        "Note: diagnostic readiness report — observed capability only, "
        "never a policy decision; no permission is assumed without "
        "probing (docs/PREFLIGHT.md has the code registry)."
    )
    return "\n".join(lines) + "\n"
