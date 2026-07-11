"""Evidence-led pain discovery: build a frozen, reproducible corpus.

Reads **public metadata only** from merged pull requests of public
repositories — changed file paths, review-comment counts and derived
keyword flags, commit counts, chronology, check-run conclusions, and
workflow-run paths. It never stores code, diffs, or comment bodies, and
it never executes anything from the observed repositories.

Outputs (committed, frozen):

- ``benchmarks/discovery/manifest.json`` — which pull requests are in
  the corpus, captured when, and their deterministic discovery/holdout
  split (``sha256(repo#number)``; last hex digit ``c``-``f`` is
  holdout, ~25%).
- ``benchmarks/discovery/analysis.json`` — per-PR mechanical facts plus
  a candidate-policy summary computed **from the discovery split
  only**; the holdout stays untouched for later validation. Negative
  results (unretrievable streams, policies that never fired) are kept,
  never pruned.

Usage (maintainer-run; CI never calls the network):

    python tools/discovery.py --repo apache/airflow --repo celery/celery \
        --repo RafineriaAI/aos-workflow-gate --per-repo 30 \
        --out-dir benchmarks/discovery
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aos_workflow_gate.collect import (  # noqa: E402
    Budget,
    _request_json,
)

API = "https://api.github.com"

MANIFEST_SCHEMA = "discovery-manifest-v0"
ANALYSIS_SCHEMA = "discovery-analysis-v0"

BOUNDARY = (
    "public metadata only: changed file paths, counts, timestamps, "
    "check conclusions, and workflow paths; no code, no diffs, no "
    "comment bodies are stored, and nothing from the observed "
    "repositories is executed"
)

_WORKFLOW_RE = re.compile(r"^\.github/workflows/[^/]+\.(yml|yaml)$")
_TEST_HARNESS_RE = re.compile(
    r"(^|/)(tests?|testing)/|(^|/)conftest\.py$|(^|/)(tox|noxfile|pytest)"
    r"\.(ini|py|toml)$|(^|/)pyproject\.toml$"
)
_SCANNER_CONFIG_RE = re.compile(
    r"(^|/)(\.pre-commit-config\.ya?ml|codecov\.ya?ml|\.codecov\.ya?ml|"
    r"sonar-project\.properties|\.github/dependabot\.ya?ml|"
    r"\.golangci\.ya?ml|\.eslintrc[^/]*|ruff\.toml|\.ruff\.toml|mypy\.ini)$"
)
_DEPENDENCY_PIN_RE = re.compile(
    r"(^|/)(requirements[^/]*\.txt|poetry\.lock|Pipfile\.lock|"
    r"package-lock\.json|yarn\.lock|pnpm-lock\.ya?ml|go\.sum|Cargo\.lock|"
    r"constraints[^/]*\.txt)$"
)
_CI_COMMENT_RE = re.compile(
    r"\b(ci|test|tests|flaky|workflow|check|pipeline|build)\b",
    re.IGNORECASE,
)

HOLDOUT_HEX = frozenset("cdef")


def split_of(repo: str, number: int) -> str:
    """Deterministic discovery/holdout assignment (~75/25)."""
    digest = hashlib.sha256(f"{repo}#{number}".encode()).hexdigest()
    return "holdout" if digest[-1] in HOLDOUT_HEX else "discovery"


def _headers(token: str | None) -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get(
    url: str, token: str | None, budget: Budget
) -> Any:
    return _request_json(
        url, _headers(token), timeout=30.0, budget=budget,
        capability="discovery",
    )


def recent_merged_pulls(
    repo: str, count: int, *, token: str | None, budget: Budget
) -> list[dict[str, Any]]:
    """Most recently created merged PRs — a mechanical, stated selection.

    "Most recent at capture time" is reproducible only through the
    frozen manifest, which is the point of freezing it.
    """
    merged: list[dict[str, Any]] = []
    for page in range(1, 6):
        payload = _get(
            f"{API}/repos/{repo}/pulls?state=closed&sort=created"
            f"&direction=desc&per_page=100&page={page}",
            token, budget,
        )
        if not isinstance(payload, list):
            break
        for pull in payload:
            if isinstance(pull, dict) and pull.get("merged_at"):
                merged.append(pull)
                if len(merged) >= count:
                    return merged
        if len(payload) < 100:
            break
    return merged


def _classify_paths(paths: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {
        "workflow": [], "test_harness": [], "scanner_config": [],
        "dependency_pins": [], "other": [],
    }
    for path in paths:
        if _WORKFLOW_RE.match(path):
            buckets["workflow"].append(path)
        elif _SCANNER_CONFIG_RE.search(path):
            buckets["scanner_config"].append(path)
        elif _TEST_HARNESS_RE.search(path):
            buckets["test_harness"].append(path)
        elif _DEPENDENCY_PIN_RE.search(path):
            buckets["dependency_pins"].append(path)
        else:
            buckets["other"].append(path)
    return buckets


def analyze_pull(
    repo: str,
    pull: dict[str, Any],
    *,
    token: str | None,
    budget: Budget,
) -> dict[str, Any]:
    """Mechanical facts for one merged PR; failures become negative
    results (``retrievable: false``), never silent omissions."""
    number = int(pull["number"])
    head_sha = str((pull.get("head") or {}).get("sha") or "")
    user = pull.get("user") or {}
    entry: dict[str, Any] = {
        "repo": repo,
        "number": number,
        "split": split_of(repo, number),
        "head_sha": head_sha,
        "chronology": {
            "created_at": pull.get("created_at"),
            "merged_at": pull.get("merged_at"),
        },
        "author": {"bot": (user.get("type") == "Bot")},
        "commits": {"count": pull.get("commits")},
    }

    paths: list[str] = []
    try:
        for page in range(1, 4):
            files = _get(
                f"{API}/repos/{repo}/pulls/{number}/files"
                f"?per_page=100&page={page}",
                token, budget,
            )
            if not isinstance(files, list) or not files:
                break
            paths.extend(
                str(item.get("filename"))
                for item in files
                if isinstance(item, dict) and item.get("filename")
            )
            if len(files) < 100:
                break
        buckets = _classify_paths(paths)
        entry["files"] = {
            "total": len(paths),
            "workflow": sorted(buckets["workflow"]),
            "test_harness_count": len(buckets["test_harness"]),
            "scanner_config": sorted(buckets["scanner_config"]),
            "dependency_pins_count": len(buckets["dependency_pins"]),
            "other_count": len(buckets["other"]),
            "retrievable": True,
        }
    except Exception as exc:  # noqa: BLE001 - recorded, not raised
        entry["files"] = {"retrievable": False, "error": str(exc)[:200]}

    try:
        comments = _get(
            f"{API}/repos/{repo}/pulls/{number}/comments?per_page=100",
            token, budget,
        )
        bodies = [
            str(comment.get("body") or "")
            for comment in comments
            if isinstance(comment, dict)
        ] if isinstance(comments, list) else []
        entry["review_comments"] = {
            "total": len(bodies),
            "ci_related": sum(
                1 for body in bodies if _CI_COMMENT_RE.search(body)
            ),
            "retrievable": True,
        }
    except Exception as exc:  # noqa: BLE001
        entry["review_comments"] = {
            "retrievable": False, "error": str(exc)[:200]
        }

    try:
        checks = _get(
            f"{API}/repos/{repo}/commits/{head_sha}/check-runs?per_page=100",
            token, budget,
        )
        runs = checks.get("check_runs") if isinstance(checks, dict) else None
        conclusions: dict[str, int] = {}
        for run in runs or []:
            if isinstance(run, dict):
                key = str(run.get("conclusion"))
                conclusions[key] = conclusions.get(key, 0) + 1
        entry["checks"] = {
            "total": sum(conclusions.values()),
            "conclusions": dict(sorted(conclusions.items())),
            "retrievable": True,
        }
    except Exception as exc:  # noqa: BLE001
        entry["checks"] = {"retrievable": False, "error": str(exc)[:200]}

    changed_workflows = set(
        (entry.get("files") or {}).get("workflow") or []
    )
    try:
        runs_payload = _get(
            f"{API}/repos/{repo}/actions/runs?head_sha={head_sha}"
            "&per_page=100",
            token, budget,
        )
        workflow_runs = (
            runs_payload.get("workflow_runs")
            if isinstance(runs_payload, dict)
            else None
        ) or []
        run_paths = [
            str(run.get("path") or "")
            for run in workflow_runs
            if isinstance(run, dict)
        ]
        self_validating = [
            path for path in run_paths if path in changed_workflows
        ]
        entry["workflow_runs"] = {
            "total": len(run_paths),
            "self_validating": len(self_validating),
            "self_validating_paths": sorted(set(self_validating)),
            "independent": len(run_paths) - len(self_validating),
            "retrievable": True,
        }
    except Exception as exc:  # noqa: BLE001
        entry["workflow_runs"] = {
            "retrievable": False, "error": str(exc)[:200]
        }
    return entry


def _fires_verifier_change(entry: dict[str, Any]) -> bool:
    files = entry.get("files") or {}
    if not files.get("retrievable"):
        return False
    return bool(
        files.get("workflow")
        or files.get("scanner_config")
        or files.get("test_harness_count")
    )


def _is_routine_bump(entry: dict[str, Any]) -> bool:
    """Mechanical routine-bump heuristic: a bot author whose change
    touches only dependency pins (no workflow/test/scanner surface)."""
    files = entry.get("files") or {}
    if not files.get("retrievable"):
        return False
    only_pins = (
        not files.get("workflow")
        and not files.get("scanner_config")
        and not files.get("test_harness_count")
        and files.get("dependency_pins_count")
        and not files.get("other_count")
    )
    return bool(entry.get("author", {}).get("bot") and only_pins)


def _fires_green_but_not_exercised(entry: dict[str, Any]) -> bool:
    checks = entry.get("checks") or {}
    if not checks.get("retrievable"):
        return False
    conclusions = checks.get("conclusions") or {}
    exercised_gap = (
        conclusions.get("skipped", 0) + conclusions.get("neutral", 0)
    )
    return bool(exercised_gap and not conclusions.get("failure"))


def summarize_policies(
    entries: list[dict[str, Any]],
) -> dict[str, Any]:
    """Candidate-policy assessment over the DISCOVERY split only.

    Every policy reports positive cases, negative controls, frequency,
    a noise assessment, and its negative results — kept even when (and
    especially when) a policy never fires.
    """
    discovery = [e for e in entries if e["split"] == "discovery"]

    def ref(entry: dict[str, Any]) -> dict[str, Any]:
        return {"repo": entry["repo"], "number": entry["number"]}

    unretrievable = [
        ref(e) for e in discovery
        if not (e.get("workflow_runs") or {}).get("retrievable")
        or not (e.get("checks") or {}).get("retrievable")
        or not (e.get("files") or {}).get("retrievable")
    ]

    verifier_hits = [e for e in discovery if _fires_verifier_change(e)]
    bumps = [e for e in verifier_hits if _is_routine_bump(e)]
    verifier_positive = [e for e in verifier_hits if not _is_routine_bump(e)]
    verifier_self_validating = [
        e for e in verifier_positive
        if (e.get("workflow_runs") or {}).get("self_validating")
    ]
    verifier_negative_controls = [
        e for e in discovery if not _fires_verifier_change(e)
    ]

    green_hits = [
        e for e in discovery if _fires_green_but_not_exercised(e)
    ]
    green_controls = [
        e for e in discovery
        if (e.get("checks") or {}).get("retrievable")
        and not _fires_green_but_not_exercised(e)
    ]

    return {
        "discovery_total": len(discovery),
        "holdout_total": len(entries) - len(discovery),
        "negative_results": {
            "unretrievable_streams": unretrievable,
            "note": (
                "kept deliberately: an unretrievable stream is a "
                "finding about evidence durability, not noise"
            ),
        },
        "verifier_change_independence": {
            "definition": (
                "a merged PR changes its own verification mechanism "
                "(workflow, test harness, or scanner config); evidence "
                "produced solely by the changed mechanism is not "
                "independent"
            ),
            "positive_cases": [ref(e) for e in verifier_positive],
            "positive_with_self_validating_runs": [
                ref(e) for e in verifier_self_validating
            ],
            "negative_controls": [
                ref(e) for e in verifier_negative_controls[:10]
            ],
            "negative_controls_total": len(verifier_negative_controls),
            "frequency": {
                "firing": len(verifier_positive),
                "of": len(discovery),
            },
            "noise": {
                "routine_bump_exclusions": [ref(e) for e in bumps],
                "routine_bump_count": len(bumps),
                "bot_authored_in_discovery": sum(
                    1 for e in discovery if e["author"]["bot"]
                ),
            },
        },
        "green_but_not_exercised": {
            "definition": (
                "a merged PR whose head commit carries skipped or "
                "neutral check conclusions and no failure: the "
                "dashboard reads green while some evidence never ran"
            ),
            "positive_cases": [ref(e) for e in green_hits],
            "negative_controls": [ref(e) for e in green_controls[:10]],
            "negative_controls_total": len(green_controls),
            "frequency": {
                "firing": len(green_hits),
                "of": len(discovery),
            },
            "noise": {
                "note": (
                    "skipped conclusions can be intentional (path "
                    "filters); the policy is advisory visibility, "
                    "not a defect claim"
                ),
            },
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", action="append", required=True)
    parser.add_argument("--per-repo", type=int, default=30)
    parser.add_argument("--out-dir", default="benchmarks/discovery")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    args = parser.parse_args(argv)

    token = os.environ.get(args.token_env)
    budget = Budget(deadline_seconds=1800.0, max_api_calls=1000)
    captured_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    manifest_pulls: list[dict[str, Any]] = []
    entries: list[dict[str, Any]] = []
    for repo in args.repo:
        pulls = recent_merged_pulls(
            repo, args.per_repo, token=token, budget=budget
        )
        print(f"{repo}: {len(pulls)} merged pull request(s)", flush=True)
        for pull in pulls:
            number = int(pull["number"])
            manifest_pulls.append(
                {
                    "repo": repo,
                    "number": number,
                    "merged_at": pull.get("merged_at"),
                    "split": split_of(repo, number),
                }
            )
            entries.append(
                analyze_pull(repo, pull, token=token, budget=budget)
            )
            print(f"  analyzed {repo}#{number}", flush=True)

    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "captured_at": captured_at,
        "boundary": BOUNDARY,
        "method": {
            "selection": (
                "most recently created merged pull requests per "
                "repository at capture time"
            ),
            "per_repo": args.per_repo,
            "split_rule": (
                "sha256('<repo>#<number>') last hex digit in c-f => "
                "holdout (~25%), else discovery"
            ),
        },
        "repositories": list(args.repo),
        "pulls": manifest_pulls,
    }
    analysis = {
        "schema_version": ANALYSIS_SCHEMA,
        "captured_at": captured_at,
        "boundary": BOUNDARY,
        "pulls": entries,
        "candidate_policies": summarize_policies(entries),
    }

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("manifest.json", manifest), ("analysis.json", analysis),
    ):
        (out_dir / name).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
            + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"wrote {out_dir / name}")
    print(f"api calls used: {budget.api_calls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
