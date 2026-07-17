"""Hybrid pre-publication value gate and claim-boundary tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical
from aos_workflow_gate.evidence import verify_record
from tools.value_gate import assess, render_markdown

ROOT = Path(__file__).resolve().parents[1]
VALUE = ROOT / "benchmarks" / "value"


def _corpus() -> dict[str, Any]:
    return json.loads((VALUE / "corpus.json").read_text(encoding="utf-8"))


def _contrasts() -> dict[str, Any]:
    return json.loads((VALUE / "exact-contrasts.json").read_text(encoding="utf-8"))


def _product_readiness(
    *,
    participants_available: bool = False,
    teams_available: bool = False,
) -> dict[str, Any]:
    readiness = json.loads(
        (VALUE / "product-test-readiness.json").read_text(encoding="utf-8")
    )
    readiness["external_access"] = {
        "participants_available": participants_available,
        "teams_available": teams_available,
    }
    return readiness


def _utility_readiness() -> dict[str, Any]:
    return json.loads(
        (VALUE / "utility-test-readiness.json").read_text(encoding="utf-8")
    )


def _utility_task_corpus() -> dict[str, Any]:
    return json.loads((VALUE / "utility-task-corpus.json").read_text(encoding="utf-8"))


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
            for _ in range(8)
        ]
    return corpus


def _assess(
    corpus: dict[str, Any],
    *,
    participants_available: bool = False,
    teams_available: bool = False,
) -> dict[str, Any]:
    return assess(
        corpus,
        product_readiness=_product_readiness(
            participants_available=participants_available,
            teams_available=teams_available,
        ),
        utility_readiness=_utility_readiness(),
        utility_task_corpus=_utility_task_corpus(),
        contrasts=_contrasts(),
    )


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


def test_committed_contrasts_are_metadata_only_and_artifact_bound() -> None:
    contrasts = _contrasts()
    assert contrasts["schema_version"] == "value-contrast-v0"
    assert len(contrasts["cases"]) == 3
    assert len({case["repository"] for case in contrasts["cases"]}) == 3
    assert _keys(contrasts).isdisjoint(
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

    full_cli = [
        case
        for case in contrasts["cases"]
        if case["aos"]["execution"] == "live_full_cli"
    ]
    assert len(full_cli) == 2
    for case in full_cli:
        aos = case["aos"]
        artifact_paths = [
            ROOT / aos["artifact_bundle"],
            ROOT / aos["artifact_policy"],
            ROOT / aos["artifact_record"],
        ]
        assert all(path.is_file() for path in artifact_paths)

        bundle = json.loads(artifact_paths[0].read_text(encoding="utf-8"))
        record = json.loads(artifact_paths[2].read_text(encoding="utf-8"))
        assert canonical.digest(bundle) == aos["bundle_digest"]
        assert record["input_bundle_digest"] == aos["bundle_digest"]
        assert record["record_digest"] == aos["record_digest"]
        assert record["verdict"] == aos["verdict"]
        assert verify_record(record)
        assert record["subject"] == bundle["subject"]
        assert record["subject"]["repository"] == case["repository"]
        assert record["subject"]["pull_request"] == case["pull_request"]
        assert record["subject"]["sha"] == case["head_sha"]
        assert aos["reason_code"] in {reason["rule"] for reason in record["reasons"]}


def test_current_evidence_separates_all_tracks() -> None:
    result = _assess(_corpus())
    assert result["status"] == "NO_GO"
    assert result["schema_version"] == "value-assessment-v3"
    assert result["metrics"]["sample_cases"] == 100
    assert result["metrics"]["repositories"] == 10
    assert result["metrics"]["self_validating_cases"] == 7
    assert result["metrics"]["self_validating_repositories"] == 5
    assert result["metrics"]["bot_signal_cases"] == 2
    assert result["metrics"]["labeled_signal_cases"] == 0
    assert result["metrics"]["exact_semantic_contrast_cases"] == 3
    assert result["metrics"]["exact_semantic_contrast_repositories"] == 3
    assert result["metrics"]["replayable_contrast_cases"] == 2
    assert result["metrics"]["required_non_independent_check_cases"] == 1
    assert result["metrics"]["independently_labeled_contrast_cases"] == 0
    assert result["criteria"]["mechanism_evidence"][0]["met"] is True
    assert result["metrics"]["precision"] is None
    assert result["tracks"] == {
        "external_test_readiness": "READY_FOR_EXTERNAL_VALIDATION",
        "external_usability": "EXTERNAL_VALIDATION_PENDING",
        "field_utility": "FIELD_VALIDATION_PENDING",
        "mechanism_evidence": "MECHANISM_CONFIRMED",
        "participant_access": "RECRUITMENT_PENDING",
        "practical_utility_testability": "UTILITY_TEST_READY",
        "product_test_readiness": "PRODUCT_TEST_READY",
        "signal_validity": "SIGNAL_INCONCLUSIVE",
        "validation_distribution": "FREE_SELF_SERVE_VALIDATION",
    }
    assert result["metrics"]["utility_task_cases"] == 8
    assert result["metrics"]["utility_readiness_checks_met"] == 7
    assert result["metrics"]["free_self_serve_validation_available"] is True
    assert result["metrics"]["validation_access"] == "free"
    assert result["metrics"]["validation_channel"] == "public_self_serve"
    assert result["metrics"]["validation_mode"] == "advisory"
    assert result["metrics"]["validation_telemetry"] == "none"
    assert result["external_test_blockers"] == []
    assert "exact_incremental_findings" in result["blockers"]
    assert "qualified_external_users" in result["blockers"]


def test_committed_assessment_regenerates_identically() -> None:
    result = _assess(_corpus())
    committed_json = (VALUE / "assessment.json").read_text(encoding="utf-8")
    regenerated_json = (
        json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    )
    assert regenerated_json == committed_json
    assert render_markdown(result) == (VALUE / "ASSESSMENT.md").read_text(
        encoding="utf-8"
    )


def test_signal_and_internal_readiness_open_only_external_validation() -> None:
    result = _assess(_fully_labeled_corpus(include_ux=False))
    assert result["metrics"]["labeled_signal_cases"] == 100
    assert result["metrics"]["precision"] == 0.99
    assert result["status"] == "NO_GO"
    assert result["tracks"]["signal_validity"] == "SIGNAL_SUPPORTED"
    assert result["tracks"]["product_test_readiness"] == "PRODUCT_TEST_READY"
    assert result["tracks"]["external_test_readiness"] == (
        "READY_FOR_EXTERNAL_VALIDATION"
    )
    assert result["tracks"]["practical_utility_testability"] == ("UTILITY_TEST_READY")
    assert result["tracks"]["validation_distribution"] == ("FREE_SELF_SERVE_VALIDATION")
    assert result["tracks"]["external_usability"] == "EXTERNAL_VALIDATION_PENDING"
    assert result["external_test_blockers"] == []
    assert result["blockers"] == [
        "controlled_comparative_study",
        "qualified_external_users",
        "next_action_clarity",
        "retention",
        "comprehension_time",
    ]


def test_legacy_user_observations_cannot_create_product_usefulness() -> None:
    result = _assess(
        _fully_labeled_corpus(include_ux=True),
        participants_available=True,
    )
    assert result["metrics"]["qualified_external_users"] == 8
    assert result["status"] == "NO_GO"
    assert result["tracks"]["external_usability"] == (
        "EXTERNAL_VALIDATION_INCONCLUSIVE"
    )
    assert "controlled_comparative_study" in result["blockers"]

    insufficient = _fully_labeled_corpus(include_ux=True)
    insufficient["ux_observations"][0]["retained_days"] = 6
    result = _assess(insufficient, participants_available=True)
    assert result["metrics"]["qualified_external_users"] == 7
    assert result["status"] == "NO_GO"
    assert result["tracks"]["external_usability"] == (
        "EXTERNAL_VALIDATION_INCONCLUSIVE"
    )


def test_internal_readiness_cannot_create_external_user_evidence() -> None:
    result = _assess(_fully_labeled_corpus(include_ux=False))
    assert result["metrics"]["product_readiness_checks_met"] == 6
    assert result["metrics"]["external_users"] == 0
    assert result["tracks"]["product_test_readiness"] == "PRODUCT_TEST_READY"
    assert result["tracks"]["external_usability"] == "EXTERNAL_VALIDATION_PENDING"
    assert result["status"] == "NO_GO"


def test_product_readiness_failure_blocks_external_validation() -> None:
    readiness = _product_readiness()
    readiness["checks"][0]["status"] = "not_met"
    result = assess(
        _fully_labeled_corpus(include_ux=False),
        product_readiness=readiness,
        utility_readiness=_utility_readiness(),
        utility_task_corpus=_utility_task_corpus(),
        contrasts=_contrasts(),
    )
    assert result["tracks"]["signal_validity"] == "SIGNAL_SUPPORTED"
    assert result["tracks"]["product_test_readiness"] == ("PRODUCT_TEST_INCOMPLETE")
    assert result["tracks"]["external_test_readiness"] == (
        "NOT_READY_FOR_EXTERNAL_VALIDATION"
    )
    assert "product_adversarial_ux" in result["external_test_blockers"]
    assert result["tracks"]["validation_distribution"] == (
        "VALIDATION_DISTRIBUTION_CLOSED"
    )


def test_missing_utility_readiness_blocks_external_validation() -> None:
    result = assess(
        _corpus(),
        product_readiness=_product_readiness(),
        contrasts=_contrasts(),
    )
    assert result["tracks"]["practical_utility_testability"] == (
        "UTILITY_TEST_INCOMPLETE"
    )
    assert result["tracks"]["external_test_readiness"] == (
        "NOT_READY_FOR_EXTERNAL_VALIDATION"
    )
    assert "utility_advisory_effect" in result["external_test_blockers"]
    assert result["tracks"]["validation_distribution"] == (
        "VALIDATION_DISTRIBUTION_CLOSED"
    )


def test_operator_label_cannot_create_precision() -> None:
    corpus = copy.deepcopy(_fully_labeled_corpus(include_ux=True))
    for case in corpus["cases"]:
        case["outcome"]["source"] = "operator"
    result = _assess(corpus, participants_available=True)
    assert result["metrics"]["labeled_signal_cases"] == 0
    assert result["metrics"]["precision"] is None
    assert result["tracks"]["signal_validity"] == "SIGNAL_INCONCLUSIVE"
    assert result["status"] == "NO_GO"


def test_one_independent_contrast_label_updates_evidence_not_publication() -> None:
    contrasts = copy.deepcopy(_contrasts())
    contrasts["cases"][0]["outcome"] = {
        "classification": "actionable_gap",
        "evidence_url": "https://example.invalid/independent/1",
        "source": "external_user",
    }
    result = assess(
        _corpus(),
        product_readiness=_product_readiness(),
        utility_readiness=_utility_readiness(),
        utility_task_corpus=_utility_task_corpus(),
        contrasts=contrasts,
    )
    assert result["metrics"]["independently_labeled_contrast_cases"] == 1
    assert result["metrics"]["actionable_exact_findings"] == 1
    assert result["metrics"]["precision"] == 1.0
    assert result["tracks"]["signal_validity"] == "SIGNAL_INCONCLUSIVE"
    assert result["status"] == "NO_GO"


def test_historical_check_states_cannot_create_an_exact_baseline() -> None:
    corpus = _fully_labeled_corpus(include_ux=True)
    for case in corpus["cases"]:
        case["github_baseline"] = {
            "exact_sha": False,
            "merge_ready": True,
            "source": "unverified_historical",
        }
    result = _assess(corpus, participants_available=True)
    assert result["metrics"]["labeled_signal_cases"] == 0
    assert result["tracks"]["signal_validity"] == "SIGNAL_INCONCLUSIVE"
    assert result["status"] == "NO_GO"


def test_precision_below_threshold_is_signal_not_supported() -> None:
    corpus = _fully_labeled_corpus(include_ux=True)
    for case in corpus["cases"][:5]:
        case["outcome"]["classification"] = "noise"
    result = _assess(corpus, participants_available=True)
    assert result["metrics"]["precision"] == 0.94
    assert "observed_precision" in result["blockers"]
    assert result["tracks"]["signal_validity"] == "SIGNAL_NOT_SUPPORTED"
    assert result["tracks"]["external_test_readiness"] == (
        "NOT_READY_FOR_EXTERNAL_VALIDATION"
    )
    assert result["external_test_blockers"] == ["signal_not_supported"]
    assert result["tracks"]["validation_distribution"] == (
        "VALIDATION_DISTRIBUTION_CLOSED"
    )
    assert result["status"] == "NO_GO"


def test_malformed_inputs_fail_closed() -> None:
    unknown = _corpus()
    unknown["unexpected"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        _assess(unknown)

    malformed_case = _corpus()
    malformed_case["cases"][0].pop("head_sha")
    with pytest.raises(ValueError, match="fields do not match"):
        _assess(malformed_case)

    float_count = _corpus()
    float_count["cases"][0]["review_comments"]["ci_related"] = 0.5
    with pytest.raises(ValueError, match="non-negative integer"):
        _assess(float_count)

    mismatched_repositories = _corpus()
    mismatched_repositories["repositories"] = mismatched_repositories["repositories"][
        :-1
    ]
    with pytest.raises(ValueError, match="sorted case repository set"):
        _assess(mismatched_repositories)

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
        _assess(nonfinite_ux, participants_available=True)

    unsupported_label = _corpus()
    unsupported_label["cases"][0]["outcome"] = {
        "classification": "actionable_gap",
        "evidence_url": None,
        "source": "external_user",
    }
    with pytest.raises(ValueError, match="requires an evidence URL"):
        _assess(unsupported_label)

    unknown_readiness = _product_readiness()
    unknown_readiness["unexpected"] = True
    with pytest.raises(ValueError, match="fields do not match"):
        assess(_corpus(), product_readiness=unknown_readiness)

    missing_check = _product_readiness()
    missing_check["checks"].pop()
    with pytest.raises(ValueError, match="frozen required check set"):
        assess(_corpus(), product_readiness=missing_check)

    unknown_utility = _utility_readiness()
    unknown_utility["unexpected"] = True
    with pytest.raises(ValueError, match="fields do not match"):
        assess(_corpus(), utility_readiness=unknown_utility)

    invalid_release_fields = _utility_readiness()
    invalid_release_fields["validation_release"]["unexpected"] = True
    with pytest.raises(ValueError, match="validation_release is invalid"):
        assess(_corpus(), utility_readiness=invalid_release_fields)

    invalid_release_mode = _utility_readiness()
    invalid_release_mode["validation_release"]["mode"] = "enforce"
    with pytest.raises(ValueError, match="must be free, public_self_serve"):
        assess(_corpus(), utility_readiness=invalid_release_mode)

    malformed_utility_digest = _utility_readiness()
    malformed_utility_digest["task_corpus"]["digest"] = "sha256:nope"
    with pytest.raises(ValueError, match="canonical sha256 digest"):
        assess(_corpus(), utility_readiness=malformed_utility_digest)

    missing_utility_check = _utility_readiness()
    missing_utility_check["checks"].pop()
    with pytest.raises(ValueError, match="frozen required check set"):
        assess(_corpus(), utility_readiness=missing_utility_check)

    inconsistent_utility_counts = _utility_readiness()
    inconsistent_utility_counts["task_corpus"]["case_count"] = 9
    with pytest.raises(ValueError, match="counts are inconsistent"):
        assess(_corpus(), utility_readiness=inconsistent_utility_counts)
    with pytest.raises(ValueError, match="requires its bound task corpus"):
        assess(_corpus(), utility_readiness=_utility_readiness())

    tampered_utility_corpus = _utility_task_corpus()
    tampered_utility_corpus["boundary"] += " mutated"
    with pytest.raises(ValueError, match="canonical digest"):
        assess(
            _corpus(),
            utility_readiness=_utility_readiness(),
            utility_task_corpus=tampered_utility_corpus,
        )
    unsafe_utility_path = _utility_readiness()
    unsafe_utility_path["task_corpus"]["path"] = "../task-corpus.json"
    with pytest.raises(ValueError, match="task_corpus.path is invalid"):
        assess(_corpus(), utility_readiness=unsafe_utility_path)

    unknown_task_field = _utility_task_corpus()
    unknown_task_field["unexpected"] = True
    with pytest.raises(ValueError, match="fields do not match"):
        assess(
            _corpus(),
            utility_readiness=_utility_readiness(),
            utility_task_corpus=unknown_task_field,
        )
    contradiction = _fully_labeled_corpus(include_ux=True)
    with pytest.raises(ValueError, match="contradict unavailable participants"):
        _assess(contradiction)


def test_malformed_contrast_corpus_fails_closed() -> None:
    unknown = _contrasts()
    unknown["cases"][0]["unexpected"] = True
    with pytest.raises(ValueError, match="fields do not match"):
        assess(_corpus(), contrasts=unknown)

    malformed_digest = _contrasts()
    malformed_digest["cases"][0]["aos"]["record_digest"] = "sha256:nope"
    with pytest.raises(ValueError, match="canonical sha256 digest"):
        assess(_corpus(), contrasts=malformed_digest)

    unsafe_artifact = _contrasts()
    unsafe_artifact["cases"][0]["aos"]["artifact_record"] = "../record.json"
    with pytest.raises(ValueError, match="artifact path is invalid"):
        assess(_corpus(), contrasts=unsafe_artifact)

    false_overlap = _contrasts()
    false_overlap["cases"][2]["required_non_independent_sources"] = ["not-required"]
    with pytest.raises(ValueError, match="not a true overlap"):
        assess(_corpus(), contrasts=false_overlap)

    inconsistent_funnel = _contrasts()
    inconsistent_funnel["method"]["topn"] = 2
    with pytest.raises(ValueError, match="method funnel is inconsistent"):
        assess(_corpus(), contrasts=inconsistent_funnel)

    false_exact_sha = _contrasts()
    false_exact_sha["cases"][0]["github"]["exact_sha"] = False
    result = assess(
        _corpus(),
        utility_readiness=_utility_readiness(),
        utility_task_corpus=_utility_task_corpus(),
        contrasts=false_exact_sha,
    )
    assert result["metrics"]["exact_semantic_contrast_cases"] == 2
    assert result["tracks"]["mechanism_evidence"] == "MECHANISM_INCOMPLETE"
    assert "exact_semantic_contrast" in result["external_test_blockers"]

    engine_artifact_claim = _contrasts()
    engine_artifact_claim["cases"][2]["aos"]["artifact_record"] = "record.json"
    with pytest.raises(ValueError, match="cannot claim canonical artifacts"):
        assess(_corpus(), contrasts=engine_artifact_claim)


def test_action_uses_shared_diagnosis_for_required_total() -> None:
    action = (ROOT / "action.yml").read_text(encoding="utf-8")
    assert "if i.get('required')" not in action
    assert "diagnose(json.load(" in action
    assert "['counts']['required_total']" in action
    assert "render_github_annotation" in action
    assert "clean(d['finding'])" in action
