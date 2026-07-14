"""Pre-publication value gate and Action diagnosis consistency."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from tools.value_gate import assess, render_markdown

ROOT = Path(__file__).resolve().parents[1]
VALUE = ROOT / "benchmarks" / "value"


def _corpus() -> dict[str, Any]:
    return json.loads((VALUE / "corpus.json").read_text(encoding="utf-8"))


def _fully_labeled_corpus(*, include_ux: bool) -> dict[str, Any]:
    corpus = _corpus()
    for index, case in enumerate(corpus["cases"]):
        case["collection_complete"] = True
        case["self_validating_workflows"] = 1
        case["github_baseline"] = {
            "exact_sha": True,
            "merge_ready": True,
            "source": "github_api_snapshot",
        }
        case["outcome"] = {
            "classification": "noise" if index == 19 else "actionable_gap",
            "evidence_url": f"https://example.invalid/evidence/{index}",
            "source": "independent_review_history",
        }
    if include_ux:
        corpus["ux_observations"] = [
            {
                "completed_runs": 3,
                "external": True,
                "kept_enabled": True,
                "next_action_clear": True,
                "retained_days": 7,
                "understood_seconds": 20,
            }
            for _ in range(5)
        ]
    return corpus


def _keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {
            nested for item in value.values() for nested in _keys(item)
        }
    if isinstance(value, list):
        return {nested for item in value for nested in _keys(item)}
    return set()


def test_committed_corpus_is_metadata_only_and_diverse() -> None:
    corpus = _corpus()
    assert corpus["schema_version"] == "value-corpus-v0"
    assert len(corpus["cases"]) == 100
    assert len({case["repository"] for case in corpus["cases"]}) == 10
    assert _keys(corpus).isdisjoint(
        {
            "annotation",
            "annotations",
            "code",
            "comment_body",
            "commit_message",
            "diff",
            "log",
            "logs",
            "patch",
        }
    )


def test_current_evidence_is_no_go_without_inventing_truth() -> None:
    result = assess(_corpus())
    assert result["status"] == "NO_GO"
    assert result["metrics"]["sample_cases"] == 100
    assert result["metrics"]["repositories"] == 10
    assert result["metrics"]["self_validating_cases"] == 7
    assert result["metrics"]["self_validating_repositories"] == 5
    assert result["metrics"]["bot_signal_cases"] == 2
    assert result["metrics"]["labeled_signal_cases"] == 0
    assert result["metrics"]["precision"] is None
    assert "exact_incremental_findings" in result["blockers"]
    assert "qualified_external_users" in result["blockers"]


def test_committed_assessment_regenerates_identically() -> None:
    result = assess(_corpus())
    committed_json = (VALUE / "assessment.json").read_text(encoding="utf-8")
    regenerated_json = (
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    assert regenerated_json == committed_json
    assert render_markdown(result) == (VALUE / "ASSESSMENT.md").read_text(
        encoding="utf-8"
    )


def test_technical_evidence_allows_only_conditional_go_without_user() -> None:
    result = assess(_fully_labeled_corpus(include_ux=False))
    assert result["metrics"]["labeled_signal_cases"] == 100
    assert result["metrics"]["precision"] == 0.99
    assert result["status"] == "CONDITIONAL_GO"
    assert result["blockers"] == [
        "qualified_external_users",
        "next_action_clarity",
        "retention",
        "comprehension_time",
    ]


def test_go_requires_clear_fast_and_retained_external_use() -> None:
    result = assess(_fully_labeled_corpus(include_ux=True))
    assert result["status"] == "GO"
    assert result["blockers"] == []

    unclear = _fully_labeled_corpus(include_ux=True)
    unclear["ux_observations"][0]["next_action_clear"] = False
    assert assess(unclear)["status"] == "CONDITIONAL_GO"

    insufficient = _fully_labeled_corpus(include_ux=True)
    insufficient["ux_observations"][0]["retained_days"] = 6
    result = assess(insufficient)
    assert result["metrics"]["qualified_external_users"] == 4
    assert result["status"] == "CONDITIONAL_GO"


def test_operator_label_cannot_create_precision() -> None:
    corpus = copy.deepcopy(_fully_labeled_corpus(include_ux=True))
    for case in corpus["cases"]:
        case["outcome"]["source"] = "operator"
    result = assess(corpus)
    assert result["metrics"]["labeled_signal_cases"] == 0
    assert result["metrics"]["precision"] is None
    assert result["status"] == "NO_GO"


def test_historical_check_states_cannot_create_an_exact_baseline() -> None:
    corpus = _fully_labeled_corpus(include_ux=True)
    for case in corpus["cases"]:
        case["github_baseline"] = {
            "exact_sha": False,
            "merge_ready": True,
            "source": "unverified_historical",
        }
    result = assess(corpus)
    assert result["metrics"]["labeled_signal_cases"] == 0
    assert result["status"] == "NO_GO"


def test_precision_below_threshold_blocks_publication() -> None:
    corpus = _fully_labeled_corpus(include_ux=True)
    for case in corpus["cases"][:5]:
        case["outcome"]["classification"] = "noise"
    result = assess(corpus)
    assert result["metrics"]["precision"] == 0.94
    assert "observed_precision" in result["blockers"]
    assert result["status"] == "NO_GO"


def test_malformed_corpus_fails_closed() -> None:
    unknown = _corpus()
    unknown["unexpected"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        assess(unknown)

    malformed_case = _corpus()
    malformed_case["cases"][0].pop("head_sha")
    with pytest.raises(ValueError, match="fields do not match"):
        assess(malformed_case)

    float_count = _corpus()
    float_count["cases"][0]["review_comments"]["ci_related"] = 0.5
    with pytest.raises(ValueError, match="non-negative integer"):
        assess(float_count)

    mismatched_repositories = _corpus()
    mismatched_repositories["repositories"] = mismatched_repositories["repositories"][
        :-1
    ]
    with pytest.raises(ValueError, match="sorted case repository set"):
        assess(mismatched_repositories)

    nonfinite_ux = _corpus()
    nonfinite_ux["ux_observations"] = [
        {
            "external": True,
            "completed_runs": 3,
            "kept_enabled": True,
            "next_action_clear": True,
            "understood_seconds": float("nan"),
            "retained_days": 7,
        }
    ]
    with pytest.raises(ValueError, match="understood_seconds is invalid"):
        assess(nonfinite_ux)

    unsupported_label = _corpus()
    unsupported_label["cases"][0]["outcome"] = {
        "classification": "actionable_gap",
        "evidence_url": None,
        "source": "external_user",
    }
    with pytest.raises(ValueError, match="requires an evidence URL"):
        assess(unsupported_label)


def test_action_uses_shared_diagnosis_for_required_total() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "if i.get('required')" not in action
    assert "diagnose(json.load(" in action
    assert "['counts']['required_total']" in action
