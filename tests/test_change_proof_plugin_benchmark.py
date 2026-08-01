from __future__ import annotations

import json
from pathlib import Path

from tools.change_proof_plugin_benchmark import (
    DEFAULT_STUDY,
    analyze,
    render_report,
)


def test_committed_change_proof_plugin_decision() -> None:
    results = analyze(DEFAULT_STUDY)

    assert results["mechanism_result"] == "PASS"
    assert results["product_direction"] == "CONTINUE_NARROW_PLUGIN_EXPERIMENT"
    assert results["default_enablement"] == "DO_NOT_ENABLE_BY_DEFAULT"
    assert results["roi_status"] == "UNPROVEN_REQUIRES_EXTERNAL_USE"


def test_adaptive_scope_avoids_behavior_preserving_noise() -> None:
    results = analyze(DEFAULT_STUDY)
    metrics = results["metrics"]

    assert metrics["observed_code_and_tests_distinguished"]["numerator"] == 5
    assert metrics["controlled_under_scoped_detected"]["numerator"] == 1
    assert metrics["behavior_preserving_raw_warnings"]["numerator"] == 2
    assert metrics["noisy_recommendations_avoided_by_scope"]["numerator"] == 2
    assert metrics["adaptive_eligible"] == 6
    assert metrics["adaptive_skipped"] == 2


def test_report_keeps_claim_and_product_boundary_plain() -> None:
    report = render_report(analyze(DEFAULT_STUDY))

    assert "would they still pass without the implementation change" in report
    assert "This is differentiated, not category-exclusive" in report
    assert "ROI remains unproven" in report
    assert "DO_NOT_ENABLE_BY_DEFAULT" in report


def test_committed_results_match_analysis() -> None:
    committed = json.loads((DEFAULT_STUDY / "results.json").read_text())

    assert committed == analyze(DEFAULT_STUDY)


def test_every_selected_case_has_complete_artifacts() -> None:
    selection = json.loads((DEFAULT_STUDY / "selection.json").read_text())

    for case in selection["cases"]:
        root = DEFAULT_STUDY / case["artifact_dir"]
        for name in ("bundle.json", "policy.json", "gate-decision.json", "source.json"):
            assert (root / name).is_file(), f"{case['case_id']}: {name}"


def test_study_root_is_repository_relative() -> None:
    assert isinstance(DEFAULT_STUDY, Path)
    assert DEFAULT_STUDY.name == "change-proof-plugin"
