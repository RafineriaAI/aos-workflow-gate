"""Internal red-team evidence for practical-utility test readiness.

The corpus proves deterministic product behavior over frozen tasks. It is
strictly separated from external comprehension, usefulness, adoption, and
commercial evidence.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aos_workflow_gate import canonical
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.evidence import build_record, observation_from_bundle
from aos_workflow_gate.policy import Policy
from aos_workflow_gate.summarize import diagnose, render_markdown
from tools.value_gate import (
    UTILITY_READINESS_SCHEMA,
    _validate_utility_binding,
    _validate_utility_readiness,
    _validate_utility_task_corpus,
    assess,
)

ROOT = Path(__file__).resolve().parents[1]
VALUE = ROOT / "benchmarks" / "value"
CORPUS_PATH = VALUE / "utility-task-corpus.json"
READINESS_PATH = VALUE / "utility-test-readiness.json"

_TOP_LEVEL_FIELDS = {"boundary", "cases", "schema_version"}
_CASE_FIELDS = {"case_id", "classification", "expected", "source"}
_EXPECTED_FIELDS = {
    "effect",
    "intact",
    "next_code",
    "primary_reason",
    "verdict",
}
_SOURCE_FIELDS = {
    "adversarial_case": {"kind", "path"},
    "bundle_policy": {"bundle", "kind", "policy"},
    "decision_record": {"kind", "path"},
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _corpus() -> dict[str, Any]:
    return _load(CORPUS_PATH)


def _readiness() -> dict[str, Any]:
    return _load(READINESS_PATH)


def _artifact(path_text: Any) -> Path:
    assert isinstance(path_text, str) and path_text
    assert "\\" not in path_text and ".." not in Path(path_text).parts
    path = ROOT / path_text
    assert path.is_file(), path_text
    return path


def _record(case: dict[str, Any]) -> dict[str, Any]:
    source = case["source"]
    kind = source["kind"]
    if kind == "decision_record":
        return _load(_artifact(source["path"]))

    if kind == "adversarial_case":
        fixture = _load(_artifact(source["path"]))
        bundle = fixture["bundle"]
        policy_value = fixture["policy"]
    else:
        assert kind == "bundle_policy"
        bundle = _load(_artifact(source["bundle"]))
        policy_value = _load(_artifact(source["policy"]))

    policy = Policy.from_dict(policy_value)
    return build_record(
        evaluate(bundle, policy),
        policy=policy,
        input_bundle_digest=canonical.digest(bundle),
        can_block=False,
        observation=observation_from_bundle(bundle),
    )


def test_utility_manifest_binds_corpus_and_evidence() -> None:
    manifest = _readiness()
    assert manifest["schema_version"] == UTILITY_READINESS_SCHEMA
    _validate_utility_readiness(manifest)

    corpus = _corpus()
    _validate_utility_task_corpus(corpus)
    _validate_utility_binding(manifest, corpus)
    binding = manifest["task_corpus"]
    assert _artifact(binding["path"]) == CORPUS_PATH
    assert binding["digest"] == canonical.digest(corpus)
    assert binding["case_count"] == len(corpus["cases"])
    assert binding["positive_controls"] == sum(
        case["classification"] == "positive_control" for case in corpus["cases"]
    )
    assert binding["negative_controls"] == sum(
        case["classification"] == "negative_control" for case in corpus["cases"]
    )

    for check in manifest["checks"]:
        for reference in check["evidence"]:
            path_text, separator, node_id = reference.partition("::")
            path = _artifact(path_text)
            assert separator and node_id, reference
            assert f"def {node_id}(" in path.read_text(encoding="utf-8"), reference


def test_utility_corpus_has_frozen_taxonomy() -> None:
    corpus = _corpus()
    assert set(corpus) == _TOP_LEVEL_FIELDS
    assert corpus["schema_version"] == "utility-task-corpus-v0"
    assert isinstance(corpus["boundary"], str) and corpus["boundary"]
    cases = corpus["cases"]
    assert isinstance(cases, list) and len(cases) == 8
    assert [case["case_id"] for case in cases] == sorted(
        case["case_id"] for case in cases
    )
    assert {case["classification"] for case in cases} == {
        "negative_control",
        "positive_control",
    }
    assert {case["expected"]["verdict"] for case in cases} == {
        "PASS",
        "WARN",
        "BLOCK",
    }

    for case in cases:
        assert set(case) == _CASE_FIELDS
        assert set(case["expected"]) == _EXPECTED_FIELDS
        source = case["source"]
        assert source["kind"] in _SOURCE_FIELDS
        assert set(source) == _SOURCE_FIELDS[source["kind"]]
        for field in set(source) - {"kind"}:
            _artifact(source[field])


def test_utility_task_corpus_replays_expected_diagnoses() -> None:
    for case in _corpus()["cases"]:
        diag = diagnose(_record(case))
        expected = case["expected"]
        assert diag["verdict"] == expected["verdict"], case["case_id"]
        assert diag["intact"] is expected["intact"], case["case_id"]
        assert diag["effect"].startswith(expected["effect"]), case["case_id"]
        assert diag["remediation"]["code"] == expected["next_code"], case["case_id"]
        assert isinstance(diag["next"], str) and diag["next"], case["case_id"]
        assert len(diag["gaps"]) <= 3, case["case_id"]

        primary = diag["gaps"][0]["rule"] if diag["gaps"] else None
        assert primary == expected["primary_reason"], case["case_id"]
        markdown, intact = render_markdown(_record(case))
        assert intact is expected["intact"], case["case_id"]
        assert (
            sum(line.startswith("**Next:**") for line in markdown.splitlines()) == 1
        ), case["case_id"]


def test_utility_task_corpus_is_deterministic() -> None:
    for case in _corpus()["cases"]:
        first = _record(case)
        second = _record(case)
        assert canonical.digest(first) == canonical.digest(second), case["case_id"]
        assert diagnose(first) == diagnose(second), case["case_id"]
        assert render_markdown(first) == render_markdown(second), case["case_id"]


def test_positive_controls_stay_quiet_pass() -> None:
    positive = [
        case
        for case in _corpus()["cases"]
        if case["classification"] == "positive_control"
    ]
    assert len(positive) == 2
    for case in positive:
        record = _record(case)
        diag = diagnose(record)
        markdown, intact = render_markdown(record)
        assert intact
        assert diag["verdict"] == "PASS"
        assert not diag["reasons"]
        assert "| Field | Value |" not in markdown
        assert len(markdown.splitlines()) <= 12


def test_utility_corpus_contains_exact_github_contrast() -> None:
    case = next(
        case
        for case in _corpus()["cases"]
        if case["case_id"] == "github-green-self-validating"
    )
    source = case["source"]
    bundle = _load(_artifact(source["bundle"]))
    collection = bundle["collection"]
    verifier = collection["verifier_change"]

    assert collection["status"] == "complete"
    assert collection["github_baseline"] == "no_required_checks"
    assert verifier["analyzed"] is True
    assert verifier["non_independent_sources"]
    assert diagnose(_record(case))["remediation"]["code"] == (
        "require_independent_evidence"
    )


def test_internal_evidence_never_proves_product_usefulness() -> None:
    result = assess(
        _load(VALUE / "corpus.json"),
        product_readiness=_load(VALUE / "product-test-readiness.json"),
        utility_readiness=_readiness(),
        utility_task_corpus=_corpus(),
        contrasts=_load(VALUE / "exact-contrasts.json"),
    )

    assert result["tracks"]["practical_utility_testability"] == ("UTILITY_TEST_READY")
    assert result["tracks"]["external_test_readiness"] == (
        "READY_FOR_EXTERNAL_VALIDATION"
    )
    assert result["tracks"]["participant_access"] == "RECRUITMENT_PENDING"
    assert result["tracks"]["external_usability"] == "EXTERNAL_VALIDATION_PENDING"
    assert result["status"] == "NO_GO"
    assert "PRODUCT_USEFUL" not in set(result["tracks"].values())
