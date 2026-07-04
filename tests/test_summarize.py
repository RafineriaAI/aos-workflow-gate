from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

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
    assert f"## Gate decision: {record['verdict']}" in text
    assert record["summary"] in text
    assert record["subject"]["repository"] in text
    assert record["policy"]["policy_id"] in text
    assert record["record_digest"] in text
    assert record["input_bundle_digest"] in text
    assert "| Record self-check | OK |" in text
    assert "UNSIGNED_NOT_OFFICIAL" in text
    for reason in record["reasons"]:
        assert reason["rule"] in text
    for source in record["inputs"]:
        assert source["id"] in text


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
