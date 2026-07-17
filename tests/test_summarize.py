from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical
from aos_workflow_gate.cli import main
from aos_workflow_gate.errors import InputError
from aos_workflow_gate.summarize import render_markdown

ROOT = Path(__file__).resolve().parents[1]
DECISION_FIXTURE = ROOT / "examples" / "gate-decision.json"


def _record() -> dict[str, Any]:
    return json.loads(DECISION_FIXTURE.read_text(encoding="utf-8"))


def test_render_markdown_covers_decision_fields() -> None:
    record = _record()
    text, intact = render_markdown(record)
    assert intact
    assert f"## AOS Workflow Gate: {record['verdict']}" in text
    assert "**What AOS found:**" in text
    assert record["subject"]["repository"] in text
    assert record["policy"]["policy_id"] in text
    assert record["record_digest"] in text
    assert record["input_bundle_digest"] in text
    assert "| Record self-check | OK |" in text
    assert "UNSIGNED\\_NOT\\_OFFICIAL" in text
    for reason in record["reasons"]:
        assert reason["rule"] in text
    for source in record["inputs"]:
        assert source["id"] in text


def test_render_markdown_top_block() -> None:
    record = _record()
    text, _ = render_markdown(record)
    assert "**What AOS found:**" in text
    assert "**Scope:**" in text
    assert "**Freshness:**" in text
    assert "**Effect:** advisory" in text
    assert "**Next:**" in text
    assert "review the named non-required check only if it matters" in text


def test_next_step_adapts_to_decision_gap() -> None:
    record = _record()
    record["verdict"] = "PASS"
    record["reasons"] = []
    for source in record["inputs"]:
        source["required"] = False
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    record["record_digest"] = canonical.digest(payload)
    text, _ = render_markdown(record)
    assert "**Next:** define required checks" in text
    assert 'required-checks: "' in text


def test_render_markdown_adds_repair_hints() -> None:
    record = _record()
    text, _ = render_markdown(record)
    assert "  - Hint: review the named non-required check only if it matters" in text


def test_render_markdown_escapes_pipes_in_table_cells() -> None:
    record = _record()
    record["inputs"][0]["id"] = "weird|id"
    text, _ = render_markdown(record)
    assert "weird\\|id" in text
    assert "| weird|id |" not in text


def test_render_markdown_reports_coverage_with_required_sources() -> None:
    record = _record()
    text, _ = render_markdown(record)
    assert "### Coverage" in text
    assert "- Required sources: 1 of 3" in text
    assert "- Blocking on: `ci.validate`" in text


def test_render_markdown_flags_decision_gap_without_required() -> None:
    record = _record()
    for source in record["inputs"]:
        source["required"] = False
    text, _ = render_markdown(record)
    assert "- Required sources: 0 of 3" in text
    assert "Decision gap" in text
    assert "cannot make this gate BLOCK" in text


def test_render_markdown_flags_tampered_record() -> None:
    record = _record()
    record["verdict"] = "PASS"
    text, intact = render_markdown(record)
    assert not intact
    assert "| Record self-check | FAILED |" in text
    assert "Do not trust this record" in text


def test_render_markdown_rejects_non_records() -> None:
    with pytest.raises(InputError):
        render_markdown(["not", "a", "record"])
    with pytest.raises(InputError):
        render_markdown({"no": "verdict"})


def test_cli_summarize_exit_codes(tmp_path: Path) -> None:
    assert main(["summarize", "--input", str(DECISION_FIXTURE)]) == 0

    tampered = _record()
    tampered["verdict"] = "PASS"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert main(["summarize", "--input", str(tampered_path)]) == 1

    malformed_path = tmp_path / "malformed.json"
    malformed_path.write_text('{"no": "verdict"}', encoding="utf-8")
    assert main(["summarize", "--input", str(malformed_path)]) == 2
