"""Adversarial regression corpus + committed contrast integrity.

Every corpus case is a frozen attack or failure shape the gate must
keep deciding correctly: the expected verdict lives ONLY here, as a
test assertion over corpus data — it is never an input to the
evaluator, and a guard asserts the evaluator code cannot even name it.
The contrast artifacts must regenerate byte-identically from committed
evidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.policy import Policy

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted((ROOT / "benchmarks" / "adversarial" / "cases").glob("*.json"))


@pytest.mark.parametrize(
    "case_path", CASES, ids=[path.stem for path in CASES]
)
def test_adversarial_case_replays(case_path: Path) -> None:
    case = json.loads(case_path.read_text(encoding="utf-8"))
    decision = evaluate(case["bundle"], Policy.from_dict(case["policy"]))
    expected = case["expected"]
    assert decision.verdict == expected["verdict"], case["case_id"]
    rules = {reason.rule for reason in decision.reasons}
    for rule in expected["reason_rules"]:
        assert rule in rules, (case["case_id"], rule)
    if expected.get("detail_contains"):
        assert any(
            expected["detail_contains"] in reason.detail
            for reason in decision.reasons
        ), (case["case_id"], expected["detail_contains"])


def test_corpus_is_nonempty_and_covers_both_failing_verdicts() -> None:
    assert len(CASES) >= 8
    verdicts = {
        json.loads(path.read_text(encoding="utf-8"))["expected"]["verdict"]
        for path in CASES
    }
    assert {"BLOCK", "WARN"} <= verdicts


def test_expected_verdict_never_reaches_the_evaluator() -> None:
    """The corpus 'expected' block is a test assertion, not an input."""
    package = ROOT / "aos_workflow_gate"
    for path in package.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "expected_verdict" not in text, path.name
        assert "adversarial" not in text, path.name


def test_contrast_artifacts_regenerate_identically(tmp_path: Path) -> None:
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
