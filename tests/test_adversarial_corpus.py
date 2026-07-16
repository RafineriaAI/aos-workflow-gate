"""Adversarial regression corpus and public proof integrity.

Decision cases freeze policy outcomes. Binding cases separately exercise
record, subject, observation-scope, and verifier-manifest correlation.
Expected outcomes remain test assertions and are never passed to product
evaluation or verification code.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.policy import Policy

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "adversarial"
CASES = sorted((CORPUS / "cases").glob("*.json"))

CLASSIFICATIONS = {
    "positive_control",
    "negative_control",
    "neutral_control",
}
REQUIRED_MECHANISMS = {
    "control_identity",
    "requirement_provenance",
    "legacy_status_boundary",
    "observation_scope",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "case_path", CASES, ids=[path.stem for path in CASES]
)
def test_adversarial_case_replays(case_path: Path) -> None:
    case = _load(case_path)
    decision = evaluate(
        case["bundle"],
        Policy.from_dict(case["policy"]),
    )
    expected = case["expected"]

    assert decision.verdict == expected["verdict"], case["case_id"]
    assert [reason.rule for reason in decision.reasons] == expected[
        "reason_rules"
    ], case["case_id"]
    if expected.get("detail_contains"):
        assert any(
            expected["detail_contains"] in reason.detail
            for reason in decision.reasons
        ), (case["case_id"], expected["detail_contains"])


def test_decision_corpus_taxonomy_and_coverage() -> None:
    assert len(CASES) >= 14
    cases = [_load(path) for path in CASES]
    assert {case["case_id"] for case in cases} == {
        path.stem for path in CASES
    }
    assert {case["classification"] for case in cases} == CLASSIFICATIONS
    assert {case["expected"]["verdict"] for case in cases} == {
        "PASS",
        "WARN",
        "BLOCK",
    }
    assert REQUIRED_MECHANISMS <= {
        case["mechanism"] for case in cases
    }


def test_expected_outcome_never_reaches_product_code() -> None:
    """Corpus expectations are test assertions, never verifier inputs."""
    package = ROOT / "aos_workflow_gate"
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "expected_verdict" not in text, path.name
        assert "adversarial" not in text, path.name


def test_adversarial_matrix_regenerates_identically() -> None:
    import tools.adversarial_matrix as matrix_module

    committed = (CORPUS / "MATRIX.md").read_text(encoding="utf-8")
    rows = matrix_module.build_rows()
    assert matrix_module.render_markdown(rows) == committed


def test_contrast_artifacts_regenerate_identically() -> None:
    import tools.contrast as contrast_module

    committed_json = (
        ROOT / "benchmarks" / "contrast" / "contrast.json"
    ).read_text(encoding="utf-8")
    committed_md = (
        ROOT / "benchmarks" / "contrast" / "CONTRAST.md"
    ).read_text(encoding="utf-8")
    contrast = contrast_module.build_contrast()
    regenerated_json = (
        json.dumps(contrast, indent=2, ensure_ascii=False, sort_keys=True)
        + "\n"
    )
    assert regenerated_json == committed_json
    assert contrast_module.render_markdown(contrast) == committed_md
    assert "../adversarial/MATRIX.md" in committed_md


def test_contrast_rows_match_committed_records() -> None:
    contrast = json.loads(
        (ROOT / "benchmarks" / "contrast" / "contrast.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(contrast["rows"]) >= 6
    for row in contrast["rows"]:
        assert row["baseline"].get("github_merge_ready") is True
        assert row["baseline"].get("declared_by") == "operator"
