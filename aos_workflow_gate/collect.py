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
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse

from . import canonical
from .errors import InputError

DEFAULT_API_URL = "https://api.github.com"
GENERATED_POLICY_ID = "collected-advisory"
API_TIMEOUT_SECONDS = 30.0
MAX_PAGES = 10
MAX_ATTEMPTS = 3
MAX_API_CALLS = 50
DEADLINE_SECONDS = 300.0
RETRY_AFTER_CAP_SECONDS = 30.0
_PER_PAGE = 100
_BACKOFF_SECONDS = (1.0, 2.0, 4.0)


@dataclass
class Budget:
    """Hard operational limits for one collection.

    Every API request consumes one call from the budget; the deadline is a
    wall-clock bound over everything including retries, backoff sleeps, and
    polling waits. Exhausting a budget is an operational error (exit 2),
    never a policy verdict.
    """

    deadline_seconds: float = DEADLINE_SECONDS
    max_api_calls: int = MAX_API_CALLS
    max_attempts: int = MAX_ATTEMPTS
    started_at: float = field(default_factory=time.monotonic)
    api_calls: int = 0

    def remaining_seconds(self) -> float:
        return self.deadline_seconds - (time.monotonic() - self.started_at)

    def take_call(self) -> None:
        if self.remaining_seconds() <= 0:
            raise InputError(
                f"collection deadline of {self.deadline_seconds:.0f}s "
                "exceeded (operational limit, not a policy verdict)"
            )
        if self.api_calls >= self.max_api_calls:
            raise InputError(
                f"collection exceeded {self.max_api_calls} API calls "
                "(operational limit, not a policy verdict)"
            )
        self.api_calls += 1

    def sleep(self, seconds: float) -> None:
        seconds = min(seconds, max(self.remaining_seconds(), 0.0))
        if seconds > 0:
            time.sleep(seconds)


def _retry_delay(error: HTTPError, attempt: int) -> float:
    retry_after = error.headers.get("Retry-After") if error.headers else None
    if retry_after:
        try:
            return min(float(retry_after), RETRY_AFTER_CAP_SECONDS)
        except ValueError:
            pass
    return _BACKOFF_SECONDS[min(attempt, len(_BACKOFF_SECONDS) - 1)]


def _is_retryable(error: HTTPError) -> bool:
    if error.code in (429,) or error.code >= 500:
        return True
    if error.code == 403 and error.headers:
        remaining = error.headers.get("X-RateLimit-Remaining")
        return remaining == "0" or bool(error.headers.get("Retry-After"))
    return False


def _request_json(
    url: str, headers: dict[str, str], *, timeout: float, budget: Budget
) -> dict[str, Any]:
    """GET a JSON document with bounded retries.

    Retries transient failures (timeouts, network errors, 429, rate-limited
    403, 5xx) with capped backoff honoring ``Retry-After``. Other HTTP
    errors fail immediately. All failures raise :class:`InputError`, which
    exits 2 — an operational error, never a policy BLOCK.
    """
    last_error: Exception | None = None
    for attempt in range(budget.max_attempts):
        budget.take_call()
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.load(response)
            if not isinstance(payload, dict):
                raise InputError("API response is not a JSON object")
            return payload
        except HTTPError as exc:
            last_error = exc
            if not _is_retryable(exc) or attempt + 1 >= budget.max_attempts:
                break
            budget.sleep(_retry_delay(exc, attempt))
        except (URLError, OSError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt + 1 >= budget.max_attempts:
                break
            budget.sleep(_BACKOFF_SECONDS[min(attempt, 2)])
    raise InputError(
        f"API request failed after {budget.max_attempts} attempt(s): "
        f"{last_error} (operational error, not a policy verdict)"
    ) from last_error


def validate_api_url(api_url: str) -> str:
    """Validate an operator-supplied API base URL.

    Only well-formed ``https`` URLs without embedded credentials, whitespace,
    or control characters are accepted; the value flows into request URLs.
    """
    if any(ch.isspace() for ch in api_url) or "\x00" in api_url:
        raise InputError("api url must not contain whitespace")
    parsed = urlparse(api_url)
    if parsed.scheme != "https":
        raise InputError(f"api url must use https, got {api_url!r}")
    if not parsed.hostname:
        raise InputError(f"api url has no host: {api_url!r}")
    if parsed.username or parsed.password:
        raise InputError("api url must not embed credentials")
    return api_url.rstrip("/")


def fetch_check_runs(
    repository: str,
    sha: str,
    *,
    token: str | None,
    api_url: str = DEFAULT_API_URL,
    timeout: float = API_TIMEOUT_SECONDS,
    max_pages: int = MAX_PAGES,
    budget: Budget | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """Fetch check runs for a commit from the GitHub API.

    ``repository`` may be ``owner/repo`` or a full project URL (GitHub
    Enterprise Server); only the ``owner/repo`` path is sent to the API.
    Pagination is followed up to ``max_pages`` pages within the budget.
    Returns the raw runs and whether the listing was truncated; on
    truncation a warning goes to stderr and uncollected required checks
    fail closed as missing.
    """
    api_url = validate_api_url(api_url)
    budget = budget or Budget()
    repo_path = repository.rstrip("/").rsplit("/", 2)
    repo_slug = "/".join(repo_path[-2:]) if len(repo_path) >= 2 else repository
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    runs: list[dict[str, Any]] = []
    total_count = 0
    for page in range(1, max_pages + 1):
        url = (
            f"{api_url}/repos/{repo_slug}/commits/{sha}/check-runs"
            f"?per_page={_PER_PAGE}&page={page}"
        )
        payload = _request_json(url, headers, timeout=timeout, budget=budget)
        page_runs = payload.get("check_runs")
        if not isinstance(page_runs, list):
            raise InputError(
                "check-runs API response has no 'check_runs' list"
            )
        raw_total = payload.get("total_count")
        total_count = raw_total if isinstance(raw_total, int) else total_count
        runs.extend(run for run in page_runs if isinstance(run, dict))
        if len(page_runs) < _PER_PAGE or len(runs) >= total_count:
            break

    truncated = total_count > len(runs)
    if truncated:
        print(
            f"warning: collected {len(runs)} of {total_count} check runs "
            "(truncated); uncollected required checks fail closed as missing",
            file=sys.stderr,
        )
    return runs, truncated


def _completed_names(runs: list[dict[str, Any]]) -> set[str]:
    return {
        run["name"]
        for run in runs
        if isinstance(run.get("name"), str) and run.get("status") == "completed"
    }


def wait_for_required(
    repository: str,
    sha: str,
    required: list[str],
    *,
    token: str | None,
    api_url: str = DEFAULT_API_URL,
    timeout: float = API_TIMEOUT_SECONDS,
    max_pages: int = MAX_PAGES,
    wait_seconds: float = 0.0,
    poll_interval: float = 10.0,
    budget: Budget | None = None,
) -> tuple[list[dict[str, Any]], bool, list[str], float]:
    """Collect check runs, polling until required checks complete.

    Polls only for the named required checks — waiting on "everything"
    has no stop condition because the gate's own job never completes while
    it waits. Returns ``(runs, truncated, incomplete_required, waited)``.
    A wait that ends with incomplete required checks is reported, not
    raised: the policy then fails closed on the missing check, and the
    bundle's collection status records why.
    """
    budget = budget or Budget()
    waited = 0.0
    while True:
        runs, truncated = fetch_check_runs(
            repository,
            sha,
            token=token,
            api_url=api_url,
            timeout=timeout,
            max_pages=max_pages,
            budget=budget,
        )
        completed = _completed_names(runs)
        incomplete = [name for name in required if name not in completed]
        if not incomplete or not required:
            return runs, truncated, incomplete, waited
        remaining_wait = min(wait_seconds - waited, budget.remaining_seconds())
        if remaining_wait <= 0:
            return runs, truncated, incomplete, waited
        step = min(poll_interval, remaining_wait)
        budget.sleep(step)
        waited += step


def build_bundle(
    runs: list[dict[str, Any]],
    *,
    repository: str,
    sha: str,
    ref: str | None = None,
    pull_request: int | None = None,
    exclude: list[str] | None = None,
    required: list[str] | None = None,
    collection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a draft-0 signal bundle from raw check-run objects.

    ``collection`` carries operational provenance (status, waits, API call
    counts); it is committed into the bundle so the decision record's
    ``input_bundle_digest`` anchors it as evidence.
    """
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
    bundle: dict[str, Any] = {
        "schema_version": "draft-0",
        "subject": subject,
        "sources": sources,
    }
    if collection is not None:
        bundle["collection"] = collection
    return bundle


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
