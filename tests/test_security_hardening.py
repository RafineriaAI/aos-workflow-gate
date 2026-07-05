from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate.collect import fetch_check_runs, validate_api_url
from aos_workflow_gate.errors import InputError
from aos_workflow_gate.paths import safe_output_path
from aos_workflow_gate.summarize import render_markdown

ROOT = Path(__file__).resolve().parents[1]
DECISION_FIXTURE = ROOT / "examples" / "gate-decision.json"


def test_safe_output_path_rejects_control_characters() -> None:
    for bad in ("a\nb.json", "a\rb.json", "a\x00b.json", "", "   "):
        with pytest.raises(InputError):
            safe_output_path(bad)
    assert safe_output_path("out/dir/record.json").name == "record.json"


def test_workspace_bound_rejects_traversal_and_absolute(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()

    inside = safe_output_path("sub/record.json", workspace=workspace)
    assert inside.is_relative_to(workspace.resolve())

    for bad in ("../escape.json", str(outside / "x.json"), "sub/../../x.json"):
        with pytest.raises(InputError, match="workspace boundary"):
            safe_output_path(bad, workspace=workspace)


def test_workspace_bound_rejects_symlink_escape(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    link = workspace / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not available on this system")
    with pytest.raises(InputError, match="workspace boundary"):
        safe_output_path("link/record.json", workspace=workspace)


def test_cli_enforces_workspace_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    monkeypatch.setenv("AOS_GATE_WORKSPACE", str(workspace))
    bundle = ROOT / "examples" / "github-pr-signal-bundle.json"
    policy = ROOT / "policies" / "default.yml"
    escape = str(tmp_path / "escape.json")
    assert (
        cli.main(
            ["evaluate", "--input", str(bundle), "--policy", str(policy),
             "--out", escape]
        )
        == 2
    )
    assert not (tmp_path / "escape.json").exists()

    assert (
        cli.main(
            ["evaluate", "--input", str(bundle), "--policy", str(policy),
             "--out", "record.json"]
        )
        == 0
    )
    assert (workspace / "record.json").exists()


def test_cli_rejects_injected_out_path(tmp_path: Path) -> None:
    bundle = ROOT / "examples" / "github-pr-signal-bundle.json"
    policy = ROOT / "policies" / "default.yml"
    injected = str(tmp_path / "x.json") + "\nverdict=PASS"
    result = cli.main(
        ["evaluate", "--input", str(bundle), "--policy", str(policy),
         "--out", injected]
    )
    assert result == 2
    assert not (tmp_path / "x.json").exists()


def test_markdown_injection_is_neutralized() -> None:
    record = json.loads(DECISION_FIXTURE.read_text(encoding="utf-8"))
    payload = "[click](https://evil.example) <img src=x> **bold** `code`"
    record["inputs"][0]["id"] = payload
    text, _ = render_markdown(record)
    assert "[click](https://evil.example)" not in text
    assert "<img src=x>" not in text
    assert "**bold**" not in text
    assert "`code`" not in text
    assert "\\[click\\]" in text and "\\<img" in text


def test_validate_api_url() -> None:
    assert validate_api_url("https://ghes.example.com/api/v3/") == (
        "https://ghes.example.com/api/v3"
    )
    for bad in (
        "http://api.github.com",
        "ftp://x",
        "https://",
        "https://user:pass@host",
        "https://host/api\n",
        "not a url",
    ):
        with pytest.raises(InputError):
            validate_api_url(bad)


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _run(run_id: int) -> dict[str, Any]:
    return {
        "id": run_id,
        "name": f"check-{run_id}",
        "head_sha": "a" * 40,
        "status": "completed",
        "conclusion": "success",
        "completed_at": "2026-07-05T00:00:00Z",
    }


def test_fetch_paginates_and_passes_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_workflow_gate import collect as collect_module

    pages = [
        {"total_count": 130, "check_runs": [_run(i) for i in range(100)]},
        {"total_count": 130, "check_runs": [_run(i) for i in range(100, 130)]},
    ]
    seen: dict[str, Any] = {"calls": 0, "timeouts": set(), "urls": []}

    def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
        seen["timeouts"].add(timeout)
        seen["urls"].append(request.full_url)
        payload = pages[seen["calls"]]
        seen["calls"] += 1
        return _FakeResponse(payload)

    monkeypatch.setattr(
        collect_module.urllib.request, "urlopen", fake_urlopen
    )
    runs, truncated = fetch_check_runs("owner/repo", "a" * 40, token=None)
    assert len(runs) == 130
    assert truncated is False
    assert seen["calls"] == 2
    assert seen["timeouts"] == {30.0}
    assert "page=1" in seen["urls"][0] and "page=2" in seen["urls"][1]


def test_fetch_warns_on_truncation(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from aos_workflow_gate import collect as collect_module

    def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
        return _FakeResponse(
            {"total_count": 5000, "check_runs": [_run(i) for i in range(100)]}
        )

    monkeypatch.setattr(
        collect_module.urllib.request, "urlopen", fake_urlopen
    )
    runs, truncated = fetch_check_runs(
        "owner/repo", "a" * 40, token=None, max_pages=2
    )
    assert len(runs) == 200
    assert truncated is True
    err = capsys.readouterr().err
    assert "truncated" in err
    assert "fail closed" in err
