"""Shared diagnostic classification (stable codes, taxonomy, remediation).

Used by two consumers that must never drift apart: the ``preflight``
command (explicit probes) and the collectors (automatic preflight —
when a collection request fails, the *failed response itself* is
classified into the same stable code with the same remediation, so the
operator gets an actionable diagnosis without a single duplicate API
call).

Codes are stable: a code never changes meaning across versions. The
registry lives in docs/PREFLIGHT.md.
"""

from __future__ import annotations

from typing import Any

_TAXONOMY = {
    "ENV": "environment",
    "PERM": "permission",
    "FEAT": "feature",
    "CTX": "context",
}

# Likely causes shown as remediation for an observed HTTP 403. These are
# suggestions derived from common token models, not assumptions the
# classification relies on: the classification itself comes only from
# the response.
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


def finding(
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
    """Classify an HTTP response into a finding, if any.

    Only the observed response is used — no permission model is assumed.
    2xx responses produce no finding here; feature-level observations
    (a capability that works but is unused) are added by the caller.
    """
    if 200 <= http_status < 300:
        return None
    if http_status == 401:
        return finding(
            "AOS-PERM-001",
            capability,
            f"HTTP 401 while probing {capability}",
            "the API rejected the credentials; the token is invalid, "
            "expired, or malformed — replace it and re-run preflight",
            "error",
        )
    if rate_limited:
        return finding(
            "AOS-PERM-004",
            capability,
            f"HTTP {http_status} rate-limited while probing {capability}",
            "the rate limit is exhausted, so capability cannot be "
            "determined now; wait for the limit window to reset, or "
            "authenticate to get a higher limit",
            "error",
        )
    if http_status == 403:
        return finding(
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
        return finding(
            "AOS-PERM-003",
            capability,
            f"HTTP 404 while probing {capability}",
            "the resource does not exist, or it exists but the token "
            "cannot see it (the API reports both identically); check "
            "the target spelling first, then the token's repository "
            "access",
            "error",
        )
    return finding(
        "AOS-ENV-002",
        capability,
        f"HTTP {http_status} while probing {capability}",
        "unexpected API response; if it persists, the endpoint may be "
        "unavailable on this server version",
        "error",
    )


def describe_failure(
    capability: str, http_status: int, *, rate_limited: bool
) -> str | None:
    """One-line diagnosis for a failed collection request.

    Rendered into the operational error so a failing first run explains
    itself with the stable code and remediation — automatic preflight
    from the failed response, with no duplicate API call.
    """
    classified = classify_response(
        capability, http_status, rate_limited=rate_limited
    )
    if classified is None:
        return None
    return (
        f"{classified['code']} [{classified['taxonomy']}] "
        f"{classified['observed']}; remediation: "
        f"{classified['remediation']}"
    )
