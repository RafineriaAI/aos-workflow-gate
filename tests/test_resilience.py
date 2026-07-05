from __future__ import annotations

import io
import json
from email.message import Message
from typing import Any
from urllib.error import HTTPError

import pytest

from aos_workflow_gate import collect as collect_module
from aos_workflow_gate.cli import main
from aos_workflow_gate.collect import Budget, fetch_check_runs, wait_for_required
from aos_workflow_gate.errors import InputError

SHA = "a" * 40


class _FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _run(name: str, status: str = "completed") -> dict[str, Any]:
    return {
        "id": 1,
        "name": name,
        "head_sha": SHA,
        "status": status,
        "conclusion": "success" if status == "completed" else None,
        "completed_at": "2026-07-05T00:00:00Z" if status == "completed" else "",
    }


def _http_error(code: int, headers: dict[str, str] | None = None) -> HTTPError:
    message = Message()
    for key, value in (headers or {}).items():
        message[key] = value
    return HTTPError("https://x", code, "err", message, io.BytesIO(b""))


def _no_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    slept: list[float] = []
    monkeypatch.setattr(
        collect_module.time, "sleep", lambda s: slept.append(s)
    )
    return slept


def test_retries_5xx_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    slept = _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(502)
        return _FakeResponse({"total_count": 1, "check_runs": [_run("ci")]})

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", fake_urlopen)
    runs, truncated = fetch_check_runs("owner/repo", SHA, token=None)
    assert len(runs) == 1 and truncated is False
    assert calls["n"] == 3
    assert slept == [1.0, 2.0]


def test_retry_after_is_honored_and_capped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept = _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        if calls["n"] == 1:
            raise _http_error(429, {"Retry-After": "7"})
        if calls["n"] == 2:
            raise _http_error(429, {"Retry-After": "999"})
        return _FakeResponse({"total_count": 0, "check_runs": []})

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", fake_urlopen)
    fetch_check_runs("owner/repo", SHA, token=None)
    assert slept == [7.0, 30.0]


def test_non_retryable_4xx_fails_immediately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_sleep(monkeypatch)
    calls = {"n": 0}

    def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
        calls["n"] += 1
        raise _http_error(404)

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(InputError, match="not a policy verdict"):
        fetch_check_runs("owner/repo", SHA, token=None)
    assert calls["n"] == 1


def test_api_call_budget_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    _no_sleep(monkeypatch)

    def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
        return _FakeResponse(
            {"total_count": 5000, "check_runs": [_run(f"c{i}") for i in range(100)]}
        )

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(InputError, match="API calls"):
        fetch_check_runs(
            "owner/repo",
            SHA,
            token=None,
            max_pages=10,
            budget=Budget(max_api_calls=3),
        )


def test_wait_for_required_polls_until_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept = _no_sleep(monkeypatch)
    calls = {"n": 0}
    states = [
        [_run("slow", status="in_progress")],
        [_run("slow")],
    ]

    def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
        payload = states[min(calls["n"], len(states) - 1)]
        calls["n"] += 1
        return _FakeResponse({"total_count": len(payload), "check_runs": payload})

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", fake_urlopen)
    runs, truncated, incomplete, waited = wait_for_required(
        "owner/repo", SHA, ["slow"], token=None,
        wait_seconds=60.0, poll_interval=10.0,
    )
    assert incomplete == []
    assert waited == 10.0
    assert slept == [10.0]
    assert calls["n"] == 2


def test_wait_timeout_reports_incomplete_not_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _no_sleep(monkeypatch)

    def fake_urlopen(request, timeout=None):  # type: ignore[no-untyped-def]
        return _FakeResponse(
            {"total_count": 1, "check_runs": [_run("slow", "in_progress")]}
        )

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", fake_urlopen)
    runs, truncated, incomplete, waited = wait_for_required(
        "owner/repo", SHA, ["slow"], token=None,
        wait_seconds=15.0, poll_interval=10.0,
    )
    assert incomplete == ["slow"]
    assert waited == 15.0


def test_can_block_reflects_enforcement(tmp_path: Any) -> None:
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    bundle = root / "examples" / "github-pr-signal-bundle.json"
    policy = root / "policies" / "default.yml"
    out = Path(tmp_path) / "r.json"

    assert main(
        ["evaluate", "--input", str(bundle), "--policy", str(policy),
         "--out", str(out)]
    ) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["can_block"] is False

    assert main(
        ["evaluate", "--input", str(bundle), "--policy", str(policy),
         "--out", str(out), "--enforce"]
    ) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["can_block"] is True
