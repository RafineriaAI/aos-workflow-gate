"""GitHub check-runs collector.

``collect`` builds a signal bundle from the GitHub check-runs API for one
commit, using the same source-digest recipe as the committed case study:
``sha256:`` over the canonical JSON of the check run's identity subset
``{check_run_id, name, head_sha, status, conclusion, completed_at}``.

Only completed check runs are collected, so the workflow run that is
currently executing the gate never gates itself. Conclusions are preserved
verbatim; only ``success`` counts as success downstream, which keeps
skipped, neutral, cancelled, and timed-out runs visible instead of silently
passing.
"""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any
from urllib.error import URLError

from . import canonical
from .errors import InputError

DEFAULT_API_URL = "https://api.github.com"
GENERATED_POLICY_ID = "collected-advisory"


def fetch_check_runs(
    repository: str, sha: str, *, token: str | None, api_url: str = DEFAULT_API_URL
) -> list[dict[str, Any]]:
    """Fetch completed check runs for a commit from the GitHub API.

    ``repository`` may be ``owner/repo`` or a full project URL (GitHub
    Enterprise Server); only the ``owner/repo`` path is sent to the API.
    """
    repo_path = repository.rstrip("/").rsplit("/", 2)
    repo_slug = "/".join(repo_path[-2:]) if len(repo_path) >= 2 else repository
    url = f"{api_url}/repos/{repo_slug}/commits/{sha}/check-runs?per_page=100"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request) as response:
            payload = json.load(response)
    except (URLError, OSError, json.JSONDecodeError) as exc:
        raise InputError(
            f"cannot fetch check runs for {repository}@{sha}: {exc}"
        ) from exc
    runs = payload.get("check_runs")
    if not isinstance(runs, list):
        raise InputError("check-runs API response has no 'check_runs' list")
    return [run for run in runs if isinstance(run, dict)]


def build_bundle(
    runs: list[dict[str, Any]],
    *,
    repository: str,
    sha: str,
    ref: str | None = None,
    pull_request: int | None = None,
    exclude: list[str] | None = None,
    required: list[str] | None = None,
) -> dict[str, Any]:
    """Build a draft-0 signal bundle from raw check-run objects."""
    excluded = set(exclude or [])
    required_names = set(required or [])
    latest: dict[str, dict[str, Any]] = {}
    for run in runs:
        name = run.get("name")
        if not isinstance(name, str) or name in excluded:
            continue
        if run.get("status") != "completed":
            continue
        current = latest.get(name)
        if current is None or _completed_at(run) > _completed_at(current):
            latest[name] = run

    sources = []
    for name in sorted(latest):
        run = latest[name]
        conclusion = run.get("conclusion")
        identity = {
            "check_run_id": run.get("id"),
            "name": name,
            "head_sha": run.get("head_sha"),
            "status": run.get("status"),
            "conclusion": conclusion,
            "completed_at": run.get("completed_at"),
        }
        sources.append(
            {
                "id": name,
                "kind": "github_check",
                "status": conclusion if isinstance(conclusion, str) else "unknown",
                "required": name in required_names,
                "observed_at": run.get("completed_at"),
                "summary": f"GitHub check run {run.get('id')} "
                f"concluded {conclusion}.",
                "digest": canonical.digest(identity),
            }
        )

    subject: dict[str, Any] = {"repository": repository, "sha": sha}
    if ref:
        subject["ref"] = ref
    if pull_request is not None:
        subject["pull_request"] = pull_request
    return {"schema_version": "draft-0", "subject": subject, "sources": sources}


def build_generated_policy(
    bundle: dict[str, Any], *, required: list[str] | None = None
) -> dict[str, Any]:
    """Build an explicit advisory policy covering every collected source.

    Sources named in ``required`` become required; every other collected
    source is advisory, so a non-success check surfaces as a warning instead
    of silently passing. The same names should be passed to ``build_bundle``
    so the bundle's per-source ``required`` flags agree with the policy.
    """
    source_ids = [source["id"] for source in bundle.get("sources", [])]
    required_ids = list(required or [])
    for required_id in required_ids:
        if required_id not in source_ids:
            raise InputError(
                f"required check {required_id!r} was not collected; "
                "it is either missing, still running, or excluded"
            )
    return {
        "schema_version": "draft-0",
        "policy_id": GENERATED_POLICY_ID,
        "mode": "advisory",
        "verification_status": "UNSIGNED_NOT_OFFICIAL",
        "subject": {"require_repository": True, "require_sha": True},
        "rules": {
            "missing_required_source": "BLOCK",
            "failed_required_source": "BLOCK",
            "malformed_input": "BLOCK",
            "advisory_warning": "WARN",
        },
        "required_sources": required_ids,
        "advisory_sources": [
            source_id for source_id in source_ids if source_id not in required_ids
        ],
    }


def resolve_github_context() -> dict[str, Any]:
    """Resolve subject identity from GitHub Actions environment variables.

    For pull_request events the head commit is taken from the event payload,
    because ``GITHUB_SHA`` points at an ephemeral merge commit there.
    """
    repository = os.environ.get("GITHUB_REPOSITORY")
    if not repository:
        raise InputError("GITHUB_REPOSITORY is not set; not a GitHub context")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    if server_url.rstrip("/") != "https://github.com":
        repository = f"{server_url.rstrip('/')}/{repository}"
    sha = os.environ.get("GITHUB_SHA")
    ref = os.environ.get("GITHUB_REF")
    pull_request: int | None = None

    event_path = os.environ.get("GITHUB_EVENT_PATH")
    if event_path and os.path.isfile(event_path):
        try:
            with open(event_path, encoding="utf-8") as handle:
                event = json.load(handle)
        except (OSError, json.JSONDecodeError):
            event = {}
        pr = event.get("pull_request")
        if isinstance(pr, dict):
            head = pr.get("head")
            if isinstance(head, dict) and isinstance(head.get("sha"), str):
                sha = head["sha"]
            if isinstance(pr.get("number"), int):
                pull_request = pr["number"]

    if not sha:
        raise InputError("cannot resolve a commit SHA from the GitHub context")
    return {
        "repository": repository,
        "sha": sha,
        "ref": ref,
        "pull_request": pull_request,
    }


def _completed_at(run: dict[str, Any]) -> str:
    value = run.get("completed_at")
    return value if isinstance(value, str) else ""
