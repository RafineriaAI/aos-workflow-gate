"""Publish an optional GitHub check without changing the AOS decision.

The check is an output transport. The verdict, process exit code, and GitHub
conclusion remain separate so callers can choose advisory reporting, CI
enforcement, and branch-protection enforcement independently.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from .collect import validate_api_url
from .errors import InputError
from .summarize import diagnose

CHECK_NAME = "AOS Workflow Gate / merge readiness"
CHECK_MODES = ("advisory", "required")
_SHA = re.compile(r"^[0-9a-fA-F]{40}$")


def conclusion_for(verdict: str, mode: str) -> str:
    """Map a decision to GitHub without changing the decision itself."""
    if mode not in CHECK_MODES:
        raise InputError(
            f"published check mode must be one of {', '.join(CHECK_MODES)}"
        )
    if verdict not in {"PASS", "WARN", "BLOCK"}:
        raise InputError(f"cannot publish unknown verdict {verdict!r}")
    if verdict == "PASS":
        return "success"
    return "neutral" if mode == "advisory" else "failure"


def _repository_slug(repository: str) -> str:
    parsed = urlparse(repository)
    path = parsed.path if parsed.scheme else repository
    parts = [part for part in path.strip("/").split("/") if part]
    if len(parts) != 2 or any(part in {".", ".."} for part in parts):
        raise InputError(f"invalid GitHub repository identity {repository!r}")
    return f"{parts[0]}/{parts[1]}"


def _run_details_url(repository: str) -> str:
    run_id = os.environ.get("GITHUB_RUN_ID")
    attempt = os.environ.get("GITHUB_RUN_ATTEMPT")
    if not run_id or not run_id.isdigit() or not attempt or not attempt.isdigit():
        raise InputError(
            "publishing a check requires GITHUB_RUN_ID and "
            "GITHUB_RUN_ATTEMPT from GitHub Actions"
        )
    server = validate_api_url(
        os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    )
    slug = _repository_slug(repository)
    return f"{server}/{slug}/actions/runs/{run_id}/attempts/{attempt}"


def _request_write(
    url: str,
    *,
    token: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    data = json.dumps(
        body, ensure_ascii=True, allow_nan=False, separators=(",", ":")
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "aos-workflow-gate",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30.0) as response:
            payload = json.load(response)
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        raise InputError(
            "GitHub decision check could not be published; grant "
            "checks: write or disable publish-check "
            f"(operational error, not a verdict): {exc}"
        ) from exc
    if not isinstance(payload, dict):
        raise InputError("GitHub decision check response is not an object")
    return payload


def _one_line(value: Any, *, limit: int = 1000) -> str:
    text = " ".join(str(value or "-").split())
    text = "".join(ch for ch in text if ch.isprintable())
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def _escape_markdown(value: Any) -> str:
    text = _one_line(value)
    for char in "\\`*_{}[]()<>#+-.!|":
        text = text.replace(char, f"\\{char}")
    return text


def publish_check(
    *,
    repository: str,
    sha: str,
    token: str | None,
    api_url: str,
    mode: str,
    record: dict[str, Any],
) -> tuple[str, int]:
    """Publish one completed, exact-SHA check from the shared diagnosis."""
    if mode not in CHECK_MODES:
        raise InputError(
            f"published check mode must be one of {', '.join(CHECK_MODES)}"
        )
    if not token:
        raise InputError(
            "publish-check requires a GitHub token with checks: write"
        )
    if not _SHA.fullmatch(sha):
        raise InputError("publish-check requires an exact 40-character head SHA")

    api_url = validate_api_url(api_url)
    slug = _repository_slug(repository)
    details_url = _run_details_url(repository)
    view = diagnose(record)
    verdict = str(view["verdict"])
    conclusion = conclusion_for(verdict, mode)
    if mode == "advisory":
        effect = "Advisory only: a non-PASS result is published as neutral."
    else:
        effect = (
            "Required mode: only PASS publishes success. Configure this check "
            "as required in GitHub rules to block merge on non-PASS."
        )
    summary = "\n".join(
        (
            f"**Verdict:** {_escape_markdown(verdict)}",
            f"**Problem:** {_escape_markdown(view['problem'])}",
            f"**Why it matters:** {_escape_markdown(view['impact'])}",
            f"**Affected area:** {_escape_markdown(view['affected_area'])}",
            f"**Severity:** {_escape_markdown(view['severity'])}",
            f"**Next step:** {_escape_markdown(view['next'])}",
            "",
            effect,
            "No source code was uploaded by this check.",
            f"Record: {_escape_markdown(record.get('record_digest'))}",
        )
    )
    payload = _request_write(
        f"{api_url}/repos/{slug}/check-runs",
        token=token,
        body={
            "name": CHECK_NAME,
            "head_sha": sha,
            "status": "completed",
            "conclusion": conclusion,
            "details_url": details_url,
            "external_id": (
                "aos-workflow-gate:"
                f"{os.environ['GITHUB_RUN_ID']}:"
                f"{os.environ['GITHUB_RUN_ATTEMPT']}"
            ),
            "output": {
                "title": _one_line(
                    f"AOS {verdict}: {view['problem']}", limit=255
                ),
                "summary": summary[:65535],
            },
        },
    )
    check_id = payload.get("id")
    if not isinstance(check_id, int) or isinstance(check_id, bool):
        raise InputError("GitHub did not return a valid decision check id")
    return conclusion, check_id
