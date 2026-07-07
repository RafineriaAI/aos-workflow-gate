from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate.cli import resolve_policy_pack
from aos_workflow_gate.errors import InputError

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40


def _run(name: str, conclusion: str = "success") -> dict[str, Any]:
    return {
        "id": 1,
        "name": name,
        "head_sha": SHA,
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": "2026-07-05T00:00:00Z",
    }


def _fake_wait(runs: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    return lambda *a, **k: (runs, False, [], 0.0)


def test_run_one_command_generated_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "wait_for_required", _fake_wait([_run("ci")]))
    monkeypatch.chdir(tmp_path)
    assert (
        cli.main(
            ["run", "--repository", "owner/repo", "--sha", SHA,
             "--require", "ci"]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "## Gate decision: PASS" in out
    record = json.loads((tmp_path / "gate-decision.json").read_text("utf-8"))
    assert record["verdict"] == "PASS"
    assert (tmp_path / ".aos-gate" / "bundle.json").is_file()
    assert (tmp_path / ".aos-gate" / "policy.json").is_file()


def test_run_enforce_exits_one_on_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cli, "wait_for_required", _fake_wait([_run("ci", "failure")])
    )
    monkeypatch.chdir(tmp_path)
    assert (
        cli.main(
            ["run", "--repository", "owner/repo", "--sha", SHA,
             "--require", "ci", "--mode", "enforce"]
        )
        == 1
    )
    record = json.loads((tmp_path / "gate-decision.json").read_text("utf-8"))
    assert record["verdict"] == "BLOCK"
    assert record["can_block"] is True


def test_run_with_policy_pack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "wait_for_required", _fake_wait([_run("ci")]))
    monkeypatch.chdir(tmp_path)
    assert (
        cli.main(
            ["run", "--repository", "owner/repo", "--sha", SHA,
             "--policy-pack", "minimal-pr-gate"]
        )
        == 0
    )
    record = json.loads((tmp_path / "gate-decision.json").read_text("utf-8"))
    assert record["policy"]["policy_id"] == "minimal-pr-gate"


def test_run_offline_with_input(tmp_path: Path) -> None:
    assert (
        cli.main(
            ["run",
             "--input", str(ROOT / "examples" / "github-pr-signal-bundle.json"),
             "--policy", str(ROOT / "policies" / "default.yml"),
             "--out", str(tmp_path / "r.json")]
        )
        == 0
    )
    record = json.loads((tmp_path / "r.json").read_text("utf-8"))
    assert record["verdict"] == "WARN"


def test_run_input_requires_policy(tmp_path: Path) -> None:
    assert (
        cli.main(
            ["run",
             "--input", str(ROOT / "examples" / "github-pr-signal-bundle.json"),
             "--out", str(tmp_path / "r.json")]
        )
        == 2
    )


def test_resolve_policy_pack_errors() -> None:
    assert resolve_policy_pack("minimal-pr-gate").name == "minimal-pr-gate.yml"
    with pytest.raises(InputError, match="available:"):
        resolve_policy_pack("does-not-exist")
    with pytest.raises(InputError, match="invalid"):
        resolve_policy_pack("../escape")


def test_evaluate_mode_alias_and_conflict(tmp_path: Path) -> None:
    bundle = ROOT / "examples" / "github-pr-signal-bundle.json"
    policy = ROOT / "policies" / "default.yml"
    assert (
        cli.main(
            ["evaluate", "--input", str(bundle), "--policy", str(policy),
             "--mode", "advisory", "--enforce"]
        )
        == 2
    )


def test_error_hint_mentions_taxonomy(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["evaluate", "--input", "missing.json",
                     "--policy", "missing.yml"]) == 2
    err = capsys.readouterr().err
    assert "USER_FAQ.md" in err
