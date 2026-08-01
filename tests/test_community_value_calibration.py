from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tools.community_value_calibration import (
    DEFAULT_STUDY,
    _sha256_portable_text_file,
    analyze,
    render_report,
)


def test_frozen_text_digest_is_independent_of_line_endings(tmp_path: Path) -> None:
    lf = tmp_path / "lf.json"
    crlf = tmp_path / "crlf.json"
    lf.write_bytes(b'{\n  "value": true\n}\n')
    crlf.write_bytes(b'{\r\n  "value": true\r\n}\r\n')

    assert _sha256_portable_text_file(lf) == _sha256_portable_text_file(crlf)


@pytest.fixture(scope="module")
def results() -> dict[str, Any]:
    return analyze(DEFAULT_STUDY)


def test_holdout_is_balanced_and_mechanically_valid(
    results: dict[str, Any],
) -> None:
    assert results["sample"] == {
        "cases": 10,
        "polish_cases": 5,
        "global_cases": 5,
    }
    assert results["mechanism_result"] == "PASS"
    assert results["metrics"]["mechanism_integrity"] == {
        "numerator": 10,
        "denominator": 10,
        "rate": 1.0,
    }
    for case in results["cases"]:
        assert case["complete"] is True
        assert case["exact_sha_bound"] is True
        assert all(case["integrity"].values())


def test_value_result_cannot_be_promoted_by_mechanism_success(
    results: dict[str, Any],
) -> None:
    metrics = results["metrics"]
    assert metrics["new_action"]["numerator"] == 0
    assert metrics["useful_explanation"]["numerator"] == 1
    assert metrics["material_alignment"] == {
        "numerator": 0,
        "denominator": 6,
        "rate": 0.0,
    }
    assert metrics["material_miss"] == {
        "numerator": 6,
        "denominator": 6,
        "rate": 1.0,
    }
    assert results["development_decision"] == "NARROW_OR_PIVOT"
    assert results["community_decision"] == "OPEN_AS_EXPERIMENTAL_PREVIEW"


def test_non_pass_messages_use_plain_main_language(
    results: dict[str, Any],
) -> None:
    assert results["metrics"]["plain_main_message"] == {
        "numerator": 7,
        "denominator": 7,
        "rate": 1.0,
    }
    non_pass = [case for case in results["cases"] if case["verdict"] != "PASS"]
    assert all(case["main_message_internal_terms"] == [] for case in non_pass)


def test_committed_outputs_match_the_analyzer(
    results: dict[str, Any],
) -> None:
    stored = json.loads((DEFAULT_STUDY / "results.json").read_text(encoding="ascii"))
    report = (DEFAULT_STUDY / "REPORT.md").read_text(encoding="utf-8")
    assert stored == results
    assert report == render_report(results)
    assert "Community use should be treated as problem discovery" in report
    assert "Wniosek po polsku" in report
