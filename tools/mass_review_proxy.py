"""Collect a bounded historical-review proxy for mass-market product value.

This study reads public pull-request metadata and review artifacts only. It
stores no raw review text and executes no repository code. Its output is a
lower-confidence proxy, never a substitute for observed product usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from tools.mass_value_study import _canonical_digest, _gh_json, _load, _rate, _write

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "benchmarks" / "mass-market" / "review-proxy-manifest.json"
DEFAULT_CORPUS = ROOT / "benchmarks" / "mass-market" / "corpus.json"
DEFAULT_OUT = ROOT / "benchmarks" / "mass-market" / "review-proxy.json"
DEFAULT_REPORT = ROOT / "benchmarks" / "mass-market" / "REVIEW_PROXY.md"

_GRAPHQL_BATCH = 2


def _selection_key(seed: str, repository: str) -> str:
    return hashlib.sha256(f"{seed}\0{repository}".encode()).hexdigest()


def select_repositories(
    manifest: dict[str, Any], corpus: dict[str, Any]
) -> list[dict[str, Any]]:
    if corpus.get("sample_digest") != manifest["source_corpus_sample_digest"]:
        raise ValueError("source corpus digest does not match review proxy manifest")
    selection = manifest["selection"]
    seed = str(selection["repository_seed"])
    quota = int(selection["repositories_per_search_language"])
    offset = int(selection.get("repository_offset_per_search_language", 0))
    groups: dict[str, list[dict[str, Any]]] = {}
    repositories = corpus.get("repositories")
    if not isinstance(repositories, list):
        raise ValueError("source corpus has no repositories")
    for row in repositories:
        if (
            not isinstance(row, dict)
            or not row.get("complete")
            or not row.get("head_sha")
        ):
            continue
        language = str(row.get("search_language"))
        groups.setdefault(language, []).append(row)
    selected: list[dict[str, Any]] = []
    for language in sorted(groups):
        ordered = sorted(
            groups[language],
            key=lambda row: _selection_key(seed, str(row["repository"])),
        )
        end = offset + quota
        if len(ordered) < end:
            raise RuntimeError(
                f"{language} has {len(ordered)} eligible repos, needs {end}"
            )
        selected.extend(ordered[offset:end])
    expected = int(selection["target_repositories"])
    if len(selected) != expected:
        raise RuntimeError(
            f"selected {len(selected)} repositories, expected {expected}"
        )
    return selected


def _gql(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _repository_query(alias: str, repository: str, candidate_prs: int) -> str:
    owner, name = repository.split("/", 1)
    return f"""
{alias}: repository(owner: {_gql(owner)}, name: {_gql(name)}) {{
  pullRequests(
    first: {candidate_prs}
    states: MERGED
    orderBy: {{field: UPDATED_AT, direction: DESC}}
  ) {{
    nodes {{
      number title url mergedAt additions deletions changedFiles
      author {{ login }}
      files(first: 100) {{
        nodes {{ path }}
        pageInfo {{ hasNextPage }}
      }}
      reviews(first: 50) {{
        nodes {{ body state submittedAt url author {{ login __typename }} }}
        pageInfo {{ hasNextPage }}
      }}
      reviewThreads(first: 50) {{
        nodes {{
          isResolved
          comments(first: 20) {{
            nodes {{ body createdAt url author {{ login __typename }} }}
            pageInfo {{ hasNextPage }}
          }}
        }}
        pageInfo {{ hasNextPage }}
      }}
    }}
  }}
}}
"""


def _batch_pull_requests(
    rows: list[dict[str, Any]], candidate_prs: int
) -> tuple[list[Any], dict[str, Any]]:
    fields = [
        _repository_query(f"r{index}", str(row["repository"]), candidate_prs)
        for index, row in enumerate(rows)
    ]
    query = "query { " + " ".join(fields) + " rateLimit { cost remaining resetAt } }"
    response = _gh_json(["graphql", "-f", f"query={query}"])
    data = response.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"GraphQL response has no data: {response.get('errors')}")
    return [data.get(f"r{index}") for index in range(len(rows))], dict(
        data.get("rateLimit") or {}
    )


def _nodes(value: Any, field: str) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    connection = value.get(field)
    if not isinstance(connection, dict) or not isinstance(
        connection.get("nodes"), list
    ):
        return []
    return [node for node in connection["nodes"] if isinstance(node, dict)]


def _has_next(value: Any, field: str) -> bool:
    if not isinstance(value, dict):
        return False
    connection = value.get(field)
    if not isinstance(connection, dict):
        return False
    page_info = connection.get("pageInfo")
    return isinstance(page_info, dict) and page_info.get("hasNextPage") is True


def _login(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    login = value.get("login")
    return str(login) if isinstance(login, str) else None


def _actor_type(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    actor_type = value.get("__typename")
    return str(actor_type) if isinstance(actor_type, str) else None


def _is_human_reviewer(
    login: str | None,
    actor_type: str | None,
    pr_author: str | None,
    manifest: dict[str, Any],
) -> bool:
    if not login or login == pr_author:
        return False
    excluded_types = manifest["human_review"].get("exclude_actor_typename", [])
    if actor_type in excluded_types:
        return False
    lowered = login.lower()
    excluded = manifest["human_review"]["excluded_login_fragments"]
    return not any(str(fragment).lower() in lowered for fragment in excluded)


def _contains_term(text: str, term: str) -> bool:
    normalized_term = " ".join(term.lower().split())
    escaped = re.escape(normalized_term).replace(r"\ ", r"\s+")
    return re.search(rf"(?<!\w){escaped}(?!\w)", text) is not None


def _categories(body: str, manifest: dict[str, Any]) -> list[str]:
    normalized = " ".join(body.lower().split())
    if not normalized:
        return []
    if any(
        _contains_term(normalized, str(term)) for term in manifest["negation_markers"]
    ):
        return []
    if not any(
        _contains_term(normalized, str(marker))
        for marker in manifest["directive_markers"]
    ):
        return []
    return sorted(
        category
        for category, terms in manifest["categories"].items()
        if any(_contains_term(normalized, str(term)) for term in terms)
    )


def _body_digest(body: str) -> str:
    normalized = " ".join(body.split()).encode("utf-8")
    return "sha256:" + hashlib.sha256(normalized).hexdigest()


def _evidence(
    *,
    author: str,
    author_type: str | None,
    body: str,
    blocking: bool,
    created_at: Any,
    resolved: bool,
    source_type: str,
    url: Any,
) -> dict[str, Any]:
    return {
        "author": author,
        "author_type": author_type,
        "blocking": blocking,
        "body_digest": _body_digest(body),
        "created_at": created_at,
        "resolved": resolved,
        "source_type": source_type,
        "url": url,
    }


def _test_path(path: str) -> bool:
    lowered = path.lower().replace("\\", "/")
    name = lowered.rsplit("/", 1)[-1]
    return (
        "/test/" in f"/{lowered}/"
        or "/tests/" in f"/{lowered}/"
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
        or name.endswith("_test.go")
        or name.endswith("_test.py")
    )


def _analyze_pull_request(
    repository: dict[str, Any], raw: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    author = _login(raw.get("author"))
    merged_at = raw.get("mergedAt")
    files = [str(node.get("path")) for node in _nodes(raw, "files")]
    evidence_by_category: dict[str, list[dict[str, Any]]] = {}
    human_artifacts = 0

    for review in _nodes(raw, "reviews"):
        login = _login(review.get("author"))
        actor_type = _actor_type(review.get("author"))
        if not _is_human_reviewer(login, actor_type, author, manifest):
            continue
        human_artifacts += 1
        body = review.get("body")
        if not isinstance(body, str):
            continue
        blocking = review.get("state") == "CHANGES_REQUESTED"
        for category in _categories(body, manifest):
            evidence_by_category.setdefault(category, []).append(
                _evidence(
                    author=str(login),
                    author_type=actor_type,
                    body=body,
                    blocking=blocking,
                    created_at=review.get("submittedAt"),
                    resolved=False,
                    source_type="pull_request_review",
                    url=review.get("url"),
                )
            )

    for thread in _nodes(raw, "reviewThreads"):
        resolved = thread.get("isResolved") is True
        for comment in _nodes(thread, "comments"):
            login = _login(comment.get("author"))
            actor_type = _actor_type(comment.get("author"))
            if not _is_human_reviewer(login, actor_type, author, manifest):
                continue
            human_artifacts += 1
            body = comment.get("body")
            if not isinstance(body, str):
                continue
            for category in _categories(body, manifest):
                evidence_by_category.setdefault(category, []).append(
                    _evidence(
                        author=str(login),
                        author_type=actor_type,
                        body=body,
                        blocking=False,
                        created_at=comment.get("createdAt"),
                        resolved=resolved,
                        source_type="review_thread_comment",
                        url=comment.get("url"),
                    )
                )

    signals = []
    for category, evidence_items in sorted(evidence_by_category.items()):
        blocking = any(item["blocking"] for item in evidence_items)
        resolved = any(item["resolved"] for item in evidence_items)
        actionable = blocking or resolved
        maintainer_action = resolved and any(
            isinstance(item.get("created_at"), str)
            and isinstance(merged_at, str)
            and item["created_at"] < merged_at
            for item in evidence_items
        )
        business_relevant = actionable and (
            blocking
            or category
            in {"security_permissions", "reliability_edge_case", "api_contract_docs"}
        )
        current_alignment = (
            category == "tests" and repository.get("coverage_gap_candidate") is True
        )
        identity = {
            "category": category,
            "number": raw.get("number"),
            "repository": repository["repository"],
        }
        signals.append(
            {
                "actionable_intervention_proxy": actionable,
                "blocking_intervention": blocking,
                "business_relevant_proxy": business_relevant,
                "current_aos_alignment_proxy": current_alignment,
                "evidence": evidence_items,
                "incremental_current_aos_proxy": (
                    business_relevant and current_alignment
                ),
                "maintainer_action_proxy": maintainer_action,
                "resolved_intervention": resolved,
                "signal_instance_id": _canonical_digest(identity),
                **identity,
            }
        )

    truncated = (
        _has_next(raw, "files")
        or _has_next(raw, "reviews")
        or _has_next(raw, "reviewThreads")
        or any(_has_next(thread, "comments") for thread in _nodes(raw, "reviewThreads"))
    )
    return {
        "additions": raw.get("additions"),
        "changed_files": raw.get("changedFiles"),
        "deletions": raw.get("deletions"),
        "final_contains_test_path": any(_test_path(path) for path in files),
        "human_review_artifacts": human_artifacts,
        "merged_at": merged_at,
        "number": raw.get("number"),
        "repository": repository["repository"],
        "search_language": repository["search_language"],
        "signals": signals,
        "star_band": repository["star_band"],
        "truncated": truncated,
        "url": raw.get("url"),
    }


def _repository_pull_requests(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, dict):
        return []
    return _nodes(raw, "pullRequests")


def collect(
    manifest_path: Path,
    corpus_path: Path,
    out_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    manifest = _load(manifest_path)
    corpus = _load(corpus_path)
    selected = select_repositories(manifest, corpus)
    selection = manifest["selection"]
    candidate_count = int(selection["candidate_pull_requests_per_repository"])
    keep_count = int(selection["pull_requests_per_repository"])
    cutoff = str(manifest["data_cutoff"])
    pull_requests: list[dict[str, Any]] = []
    repository_rows: list[dict[str, Any]] = []
    last_rate: dict[str, Any] = {}

    for offset in range(0, len(selected), _GRAPHQL_BATCH):
        batch = selected[offset : offset + _GRAPHQL_BATCH]
        raw_repositories, last_rate = _batch_pull_requests(batch, candidate_count)
        for repository, raw_repository in zip(batch, raw_repositories, strict=True):
            eligible = [
                pr
                for pr in _repository_pull_requests(raw_repository)
                if isinstance(pr.get("mergedAt"), str) and str(pr["mergedAt"]) <= cutoff
            ][:keep_count]
            analyzed = [
                _analyze_pull_request(repository, pr, manifest) for pr in eligible
            ]
            pull_requests.extend(analyzed)
            repository_rows.append(
                {
                    "collection_complete": raw_repository is not None,
                    "coverage_gap_candidate": repository["coverage_gap_candidate"],
                    "pull_requests_collected": len(analyzed),
                    "repository": repository["repository"],
                    "search_language": repository["search_language"],
                    "selection_key": _selection_key(
                        str(selection["repository_seed"]),
                        str(repository["repository"]),
                    ),
                    "star_band": repository["star_band"],
                }
            )
        print(
            f"review proxy {min(offset + len(batch), len(selected))}/{len(selected)}",
            file=sys.stderr,
        )

    result = _result(manifest, corpus, repository_rows, pull_requests, last_rate)
    _write(out_path, result)
    report_path.write_text(
        render_report(manifest, result), encoding="utf-8", newline="\n"
    )
    return result


def _result(
    manifest: dict[str, Any],
    corpus: dict[str, Any],
    repositories: list[dict[str, Any]],
    pull_requests: list[dict[str, Any]],
    rate_limit: dict[str, Any],
) -> dict[str, Any]:
    signals = [signal for pr in pull_requests for signal in pr["signals"]]
    actionable = [s for s in signals if s["actionable_intervention_proxy"]]
    business = [s for s in actionable if s["business_relevant_proxy"]]
    aligned = [s for s in actionable if s["current_aos_alignment_proxy"]]
    incremental = [s for s in business if s["incremental_current_aos_proxy"]]
    prs_with_review = [pr for pr in pull_requests if pr["human_review_artifacts"] > 0]
    prs_actionable = [
        pr
        for pr in pull_requests
        if any(s["actionable_intervention_proxy"] for s in pr["signals"])
    ]
    metrics = {
        "actionable_signal_instances": len(actionable),
        "business_relevant_signal_instances": len(business),
        "business_relevant_incremental_rate": _rate(len(incremental), len(business)),
        "current_aos_aligned_instances": len(aligned),
        "current_aos_alignment_among_actionable": _rate(len(aligned), len(actionable)),
        "human_review_artifacts": sum(
            int(pr["human_review_artifacts"]) for pr in pull_requests
        ),
        "maintainer_action_proxy_instances": sum(
            bool(signal["maintainer_action_proxy"]) for signal in signals
        ),
        "pull_requests_actionable": len(prs_actionable),
        "pull_requests_collected": len(pull_requests),
        "pull_requests_truncated": sum(bool(pr["truncated"]) for pr in pull_requests),
        "pull_requests_with_human_review": len(prs_with_review),
        "repositories_collected": sum(
            bool(repository["collection_complete"]) for repository in repositories
        ),
        "repositories_selected": len(repositories),
        "review_actionable_pain_rate": _rate(len(prs_actionable), len(prs_with_review)),
        "review_intervention_instances": len(signals),
    }
    thresholds = manifest["thresholds"]
    sample_ok = (
        metrics["pull_requests_collected"]
        >= thresholds["minimum_pull_requests_collected"]
        and metrics["pull_requests_with_human_review"]
        >= thresholds["minimum_pull_requests_with_human_review"]
    )
    pain_ok = (
        metrics["review_actionable_pain_rate"] is not None
        and metrics["review_actionable_pain_rate"]
        >= thresholds["review_actionable_pain_rate_min"]
    )
    alignment_ok = (
        metrics["current_aos_alignment_among_actionable"] is not None
        and metrics["current_aos_alignment_among_actionable"]
        >= thresholds["current_aos_alignment_among_actionable_min"]
    )
    incremental_ok = (
        metrics["business_relevant_incremental_rate"] is not None
        and metrics["business_relevant_incremental_rate"]
        >= thresholds["business_relevant_incremental_rate_min"]
    )
    if not sample_ok:
        status = "INSUFFICIENT_PROXY_SAMPLE"
    elif pain_ok and alignment_ok and incremental_ok:
        status = "PROXY_SUPPORT_CURRENT_VALUE"
    elif pain_ok:
        status = "REAL_PAIN_FOUND_AOS_GAP"
    else:
        status = "PROXY_NO_CLEAR_PAIN"
    return {
        "category_counts": dict(
            sorted(Counter(str(signal["category"]) for signal in signals).items())
        ),
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "corpus_digest": _canonical_digest(corpus),
        "github_rate_limit_after_collection": rate_limit,
        "manifest_digest": _canonical_digest(manifest),
        "metrics": metrics,
        "pull_requests": pull_requests,
        "repositories": repositories,
        "schema_version": "aos-mass-review-proxy-result/v0",
        "status": status,
        "study_id": manifest["study_id"],
        "threshold_checks": {
            "alignment": alignment_ok,
            "business_relevant_incremental": incremental_ok,
            "pain": pain_ok,
            "sample": sample_ok,
        },
    }


def _pct(value: Any) -> str:
    return "n/a" if value is None else f"{100 * float(value):.1f}%"


def render_report(manifest: dict[str, Any], result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    lines = [
        "# Historical review pain proxy",
        "",
        f"Status: `{result['status']}`.",
        "",
        "## Boundary",
        "",
        str(manifest["classification"]["limitations"]),
        "",
        "This is a deterministic keyword-and-state proxy over public history. It",
        "does not show how a maintainer reacts to AOS and cannot establish causality,",
        "decision change, acceptance, retention, willingness to pay, or precision.",
        "Raw review text is not stored; public URLs and body digests preserve audit",
        "references.",
        "",
        "## Sample",
        "",
        f"- Repositories selected: **{metrics['repositories_selected']}**; collected: "
        f"**{metrics['repositories_collected']}**.",
        f"- Merged PRs: **{metrics['pull_requests_collected']}**.",
        "- PRs with eligible human review: "
        f"**{metrics['pull_requests_with_human_review']}**.",
        f"- Human review artifacts: **{metrics['human_review_artifacts']}**.",
        f"- Truncated PR observations: **{metrics['pull_requests_truncated']}**.",
        "",
        "## Results",
        "",
        "- PRs with actionable review pain: "
        f"**{metrics['pull_requests_actionable']}** "
        f"({_pct(metrics['review_actionable_pain_rate'])} of reviewed PRs).",
        f"- Actionable signal instances: **{metrics['actionable_signal_instances']}**.",
        "- Current AOS alignment among actionable instances: "
        f"**{_pct(metrics['current_aos_alignment_among_actionable'])}**.",
        "- Business-relevant incremental alignment: "
        f"**{_pct(metrics['business_relevant_incremental_rate'])}**.",
        "- Maintainer-action proxy instances: "
        f"**{metrics['maintainer_action_proxy_instances']}**.",
        "",
        "| Category | Interventions |",
        "| --- | ---: |",
    ]
    for category, count in result["category_counts"].items():
        lines.append(f"| {category} | {count} |")
    lines += [
        "",
        "## Interpretation",
        "",
        "`REAL_PAIN_FOUND_AOS_GAP` means reviewers demonstrably intervene on daily",
        "changes, but the current project-level AOS signal rarely aligns with those",
        "interventions. This supports product discovery, not a product-value claim.",
        "",
        "## Integrity",
        "",
        f"- Manifest digest: `{result['manifest_digest']}`.",
        f"- Source corpus digest: `{result['corpus_digest']}`.",
        "",
    ]
    return "\n".join(lines)


def combine(
    manifest_path: Path,
    corpus_path: Path,
    phase_paths: list[Path],
    out_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    manifest = _load(manifest_path)
    corpus = _load(corpus_path)
    phases = [_load(path) for path in phase_paths]
    if len(phases) < 2:
        raise ValueError("combined review proxy requires at least two phases")
    expected_phase_digest = manifest.get("source_phase_result_digest")
    if expected_phase_digest and _canonical_digest(phases[0]) != expected_phase_digest:
        raise ValueError("phase 1 digest does not match extension manifest")
    repositories = [row for phase in phases for row in phase["repositories"]]
    pull_requests = [row for phase in phases for row in phase["pull_requests"]]
    repository_ids = [str(row["repository"]) for row in repositories]
    if len(repository_ids) != len(set(repository_ids)):
        raise ValueError("combined phases contain overlapping repositories")
    pull_request_ids = [
        (str(row["repository"]), int(row["number"])) for row in pull_requests
    ]
    if len(pull_request_ids) != len(set(pull_request_ids)):
        raise ValueError("combined phases contain overlapping pull requests")
    result = _result(manifest, corpus, repositories, pull_requests, {})
    result["combined"] = True
    result["phase_digests"] = [
        {"path": path.name, "result_digest": _canonical_digest(phase)}
        for path, phase in zip(phase_paths, phases, strict=True)
    ]
    _write(out_path, result)
    report_path.write_text(
        render_report(manifest, result), encoding="utf-8", newline="\n"
    )
    return result


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--phase", action="append", default=[], type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.phase:
        result = combine(args.manifest, args.corpus, args.phase, args.out, args.report)
    else:
        result = collect(args.manifest, args.corpus, args.out, args.report)
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
