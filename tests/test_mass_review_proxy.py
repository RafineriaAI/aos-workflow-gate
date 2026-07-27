"""Regression tests for the historical review pain proxy."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from tools.mass_review_proxy import (
    _analyze_pull_request,
    _categories,
    _is_human_reviewer,
    select_repositories,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "benchmarks" / "mass-market" / "review-proxy-manifest.json"


def _manifest() -> dict[str, Any]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def test_category_classifier_requires_directive_and_rejects_negation() -> None:
    manifest = _manifest()

    assert _categories("Please add tests for this edge case.", manifest) == [
        "reliability_edge_case",
        "tests",
    ]
    assert _categories("The test coverage is 90 percent.", manifest) == []
    assert _categories("No need to add tests here.", manifest) == []
    assert _categories("Please use the latest release.", manifest) == []
    assert _categories("Please use the available image path.", manifest) == []


def test_github_actor_type_excludes_bots_independent_of_login() -> None:
    manifest = json.loads(
        (
            ROOT
            / "benchmarks"
            / "mass-market"
            / "review-proxy-correction-manifest.json"
        ).read_text(encoding="utf-8")
    )

    assert not _is_human_reviewer("coderabbitai", "Bot", "author", manifest)
    assert _is_human_reviewer("reviewer", "User", "author", manifest)


def test_repository_selection_is_deterministic_and_language_stratified() -> None:
    manifest = _manifest()
    manifest["source_corpus_sample_digest"] = "sample"
    manifest["selection"]["repositories_per_search_language"] = 1
    manifest["selection"]["target_repositories"] = 2
    corpus = {
        "sample_digest": "sample",
        "repositories": [
            {
                "complete": True,
                "head_sha": "a" * 40,
                "repository": "example/python-a",
                "search_language": "Python",
            },
            {
                "complete": True,
                "head_sha": "b" * 40,
                "repository": "example/python-b",
                "search_language": "Python",
            },
            {
                "complete": True,
                "head_sha": "c" * 40,
                "repository": "example/go",
                "search_language": "Go",
            },
            {
                "complete": True,
                "head_sha": "d" * 40,
                "repository": "example/go-b",
                "search_language": "Go",
            },
        ],
    }

    first = select_repositories(manifest, corpus)
    second = select_repositories(manifest, copy.deepcopy(corpus))

    assert first == second
    assert {row["search_language"] for row in first} == {"Go", "Python"}
    extension = copy.deepcopy(manifest)
    extension["selection"]["repository_offset_per_search_language"] = 1
    next_rows = select_repositories(extension, corpus)
    assert {row["repository"] for row in first}.isdisjoint(
        {row["repository"] for row in next_rows}
    )


def test_pull_request_analysis_stores_digest_and_url_not_review_text() -> None:
    manifest = _manifest()
    repository = {
        "coverage_gap_candidate": True,
        "repository": "example/project",
        "search_language": "Python",
        "star_band": "10..99",
    }
    review_text = "Please add tests for this edge case."
    raw = {
        "additions": 10,
        "author": {"login": "author"},
        "changedFiles": 2,
        "deletions": 1,
        "files": {
            "nodes": [{"path": "tests/test_change.py"}],
            "pageInfo": {"hasNextPage": False},
        },
        "mergedAt": "2026-01-02T00:00:00Z",
        "number": 7,
        "reviews": {
            "nodes": [
                {
                    "author": {"login": "reviewer"},
                    "body": review_text,
                    "state": "CHANGES_REQUESTED",
                    "submittedAt": "2026-01-01T00:00:00Z",
                    "url": "https://example.invalid/review/1",
                }
            ],
            "pageInfo": {"hasNextPage": False},
        },
        "reviewThreads": {"nodes": [], "pageInfo": {"hasNextPage": False}},
        "url": "https://example.invalid/pull/7",
    }

    result = _analyze_pull_request(repository, raw, manifest)

    assert result["human_review_artifacts"] == 1
    assert result["final_contains_test_path"] is True
    assert {signal["category"] for signal in result["signals"]} == {
        "reliability_edge_case",
        "tests",
    }
    tests_signal = next(
        signal for signal in result["signals"] if signal["category"] == "tests"
    )
    assert tests_signal["blocking_intervention"] is True
    assert tests_signal["current_aos_alignment_proxy"] is True
    assert review_text not in json.dumps(result)
