from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical
from aos_workflow_gate.cli import main
from aos_workflow_gate.errors import InputError
from aos_workflow_gate.export import PREDICATE_TYPE, STATEMENT_TYPE, build_statement

ROOT = Path(__file__).resolve().parents[1]
DECISION_FIXTURE = ROOT / "examples" / "aos-kernel-gate-decision.json"


def _record() -> dict[str, Any]:
    return json.loads(DECISION_FIXTURE.read_text(encoding="utf-8"))


def test_build_statement_wraps_record() -> None:
    record = _record()
    statement = build_statement(record)
    assert statement["_type"] == STATEMENT_TYPE
    assert statement["predicateType"] == PREDICATE_TYPE
    assert statement["predicate"] == record
    (subject,) = statement["subject"]
    assert subject["digest"] == {"gitCommit": record["subject"]["sha"]}
    assert subject["name"].startswith("git+https://github.com/")
    assert record["subject"]["repository"] in subject["name"]


def test_build_statement_refuses_tampered_record() -> None:
    record = _record()
    record["verdict"] = "PASS" if record["verdict"] != "PASS" else "WARN"
    with pytest.raises(InputError, match="self-digest"):
        build_statement(record)


def test_build_statement_requires_git_sha() -> None:
    record = _record()
    record["subject"]["sha"] = "not-a-sha"
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    record["record_digest"] = canonical.digest(payload)
    with pytest.raises(InputError, match="gitCommit"):
        build_statement(record)


def test_cli_export_writes_statement(tmp_path: Path) -> None:
    out = tmp_path / "statement.json"
    assert (
        main(["export", "--input", str(DECISION_FIXTURE), "--out", str(out)]) == 0
    )
    statement = json.loads(out.read_text(encoding="utf-8"))
    assert statement["predicateType"] == PREDICATE_TYPE

    tampered = _record()
    tampered["summary"] = "edited"
    tampered_path = tmp_path / "tampered.json"
    tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert main(["export", "--input", str(tampered_path)]) == 2
