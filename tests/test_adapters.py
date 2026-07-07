from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate.adapters import sarif_source, scorecard_source
from aos_workflow_gate.collect import build_bundle
from aos_workflow_gate.errors import InputError

SHA = "a" * 40


def _sarif(tmp_path: Path, results: list[dict[str, Any]]) -> Path:
    payload = {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "Demo Scanner", "version": "1.2"}},
                "results": results,
            }
        ],
    }
    path = tmp_path / "scan.sarif"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_sarif_mapping_contract(tmp_path: Path) -> None:
    error = sarif_source(_sarif(tmp_path, [{"level": "error"}, {"level": "note"}]))
    assert error["status"] == "failure"
    assert error["id"] == "sarif.demo-scanner"
    assert "1 error(s)" in error["summary"]

    warn = sarif_source(_sarif(tmp_path, [{"level": "note"}, {}]))
    assert warn["status"] == "warning"

    clean = sarif_source(_sarif(tmp_path, []))
    assert clean["status"] == "success"
    assert clean["signal_source"] == "sarif_file"


def test_sarif_digest_is_stable(tmp_path: Path) -> None:
    a = sarif_source(_sarif(tmp_path, [{"level": "warning"}]))
    b = sarif_source(_sarif(tmp_path, [{"level": "warning"}]))
    assert a["digest"] == b["digest"]


def test_sarif_rejects_malformed(tmp_path: Path) -> None:
    bad = tmp_path / "bad.sarif"
    bad.write_text("{}", encoding="utf-8")
    with pytest.raises(InputError, match="runs"):
        sarif_source(bad)


def test_scorecard_presence_source(tmp_path: Path) -> None:
    path = tmp_path / "score.json"
    path.write_text(
        json.dumps({"score": 7.5, "checks": [{}, {}, {}]}), encoding="utf-8"
    )
    source = scorecard_source(path)
    assert source["status"] == "success"
    assert "7.5/10" in source["summary"]
    assert "not as a verdict" not in source["summary"]

    path.write_text(json.dumps({"checks": []}), encoding="utf-8")
    with pytest.raises(InputError, match="score"):
        scorecard_source(path)


def test_adapter_sources_merge_and_required(tmp_path: Path) -> None:
    run = {
        "id": 1,
        "name": "ci",
        "head_sha": SHA,
        "status": "completed",
        "conclusion": "success",
        "completed_at": "2026-07-05T00:00:00Z",
    }
    sarif = sarif_source(_sarif(tmp_path, []))
    bundle = build_bundle(
        [run],
        repository="owner/repo",
        sha=SHA,
        required=["ci", sarif["id"]],
        extra_sources=[sarif],
    )
    by_id = {s["id"]: s for s in bundle["sources"]}
    assert by_id[sarif["id"]]["required"] is True
    assert [s["id"] for s in bundle["sources"]] == sorted(by_id)

    colliding = dict(sarif, id="ci")
    with pytest.raises(InputError, match="collides"):
        build_bundle(
            [run], repository="owner/repo", sha=SHA, extra_sources=[colliding]
        )
