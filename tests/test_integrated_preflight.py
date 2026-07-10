from __future__ import annotations

import io
import json
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate.collect import Budget, _request_json
from aos_workflow_gate.diagnostics import describe_failure
from aos_workflow_gate.errors import InputError
from aos_workflow_gate.requirements import requirement_snapshot

SHA = "b" * 40


def _http_error(code: int) -> HTTPError:
    return HTTPError(
        "https://api.github.com/x", code, f"HTTP {code}", Message(),
        io.BytesIO(b""),
    )


def test_describe_failure_carries_code_and_remediation() -> None:
    text = describe_failure("check_runs", 403, rate_limited=False)
    assert text is not None
    assert "AOS-PERM-002" in text
    assert "[permission]" in text
    assert "remediation:" in text
    assert describe_failure("check_runs", 200, rate_limited=False) is None


def test_request_json_enriches_final_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_workflow_gate import collect as collect_module

    def opener(request: Any, timeout: float | None = None) -> Any:
        raise _http_error(403)

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    with pytest.raises(InputError) as excinfo:
        _request_json(
            "https://api.github.com/repos/o/r/commits/x/check-runs",
            {},
            timeout=1.0,
            budget=Budget(),
            capability="check_runs",
        )
    message = str(excinfo.value)
    assert "AOS-PERM-002" in message
    assert "checks: read" in message
    assert "can_continue: no" in message
    assert "not a policy verdict" in message


def test_request_json_404_names_the_ambiguity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_workflow_gate import collect as collect_module

    monkeypatch.setattr(
        collect_module.urllib.request,
        "urlopen",
        lambda request, timeout=None: (_ for _ in ()).throw(_http_error(404)),
    )
    with pytest.raises(InputError, match="AOS-PERM-003"):
        _request_json(
            "https://api.github.com/repos/o/r", {},
            timeout=1.0, budget=Budget(), capability="repository",
        )


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


RULES = [
    {
        "type": "required_status_checks",
        "parameters": {
            "required_status_checks": [
                {"context": "ci", "integration_id": 15368},
                {"context": "legacy-gate"},
            ]
        },
    }
]


def _run(name: str) -> dict[str, Any]:
    return {
        "id": 1,
        "name": name,
        "head_sha": SHA,
        "status": "completed",
        "conclusion": "success",
        "completed_at": "2026-07-10T00:00:00Z",
        "app": {"id": 15368},
    }


def _opener_with_broken_statuses(runs: list[dict[str, Any]]) -> Any:
    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        if "/rules/branches/" in url:
            return _FakeResponse(RULES)
        if url.endswith("/status"):
            raise _http_error(403)
        if "/pulls/" in url:
            return _FakeResponse(
                {
                    "head": {"sha": SHA, "repo": {"full_name": "octo/repo"}},
                    "base": {"ref": "main", "repo": {"full_name": "octo/repo"}},
                    "state": "open",
                    "merged": False,
                    "draft": False,
                }
            )
        return _FakeResponse({"total_count": len(runs), "check_runs": runs})
    return opener


def test_snapshot_degrades_statuses_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_workflow_gate import collect as collect_module

    monkeypatch.setattr(
        collect_module.urllib.request,
        "urlopen",
        _opener_with_broken_statuses([_run("ci")]),
    )
    snapshot = requirement_snapshot(
        api_url="https://api.github.com",
        slug="octo/repo",
        repository="octo/repo",
        sha=SHA,
        branch="main",
        token=None,
        budget=Budget(),
    )
    assert "AOS-PERM-002" in snapshot["statuses_unverifiable"]
    states = {c["context"]: c for c in snapshot["controls"]}
    assert states["ci"]["state"] == "satisfied"
    # the control only the status stream could satisfy is unverifiable,
    # not silently missing
    assert states["legacy-gate"]["state"] == "unverifiable"
    assert states["legacy-gate"]["observed"]["statuses_stream"] == (
        "unreadable"
    )


def test_check_pr_continues_when_statuses_degrade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from aos_workflow_gate import collect as collect_module

    monkeypatch.setattr(
        collect_module.urllib.request,
        "urlopen",
        _opener_with_broken_statuses([_run("ci")]),
    )
    monkeypatch.chdir(tmp_path)
    assert cli.main(["check-pr", "https://github.com/octo/repo/pull/7"]) == 0
    out = capsys.readouterr().out
    assert "can_continue: yes" in out
    record = json.loads((tmp_path / "gate-decision.json").read_text("utf-8"))
    assert record["verdict"] == "BLOCK"  # legacy-gate fails closed
    bundle = json.loads(
        (tmp_path / ".aos-gate" / "bundle.json").read_text("utf-8")
    )
    assert "AOS-PERM-002" in bundle["collection"]["statuses_unverifiable"]
    requirements = {
        req["context"]: req["state"]
        for req in bundle["collection"]["requirements"]
    }
    assert requirements["legacy-gate"] == "unverifiable"
