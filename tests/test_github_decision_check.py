from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.request import Request

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate import requirements as requirements_module
from aos_workflow_gate.collect import Budget
from aos_workflow_gate.errors import InputError
from aos_workflow_gate.github_decision_check import (
    CHECK_NAME,
    conclusion_for,
    publish_check,
)

ROOT = Path(__file__).resolve().parents[1]
SHA = "a" * 40
APP_ID = 15368


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _request_body(request: Request) -> dict[str, Any]:
    data = request.data
    assert isinstance(data, bytes)
    value = json.loads(data.decode("utf-8"))
    assert isinstance(value, dict)
    return value


def _record() -> dict[str, Any]:
    value = json.loads(
        (ROOT / "examples" / "gate-decision.json").read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return value


def _set_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    monkeypatch.setenv("GITHUB_SERVER_URL", "https://github.com")
    monkeypatch.setenv("GITHUB_TOKEN", "token")


def test_conclusion_is_independent_from_verdict() -> None:
    assert conclusion_for("PASS", "advisory") == "success"
    assert conclusion_for("PASS", "required") == "success"
    assert conclusion_for("WARN", "advisory") == "neutral"
    assert conclusion_for("BLOCK", "advisory") == "neutral"
    assert conclusion_for("WARN", "required") == "failure"
    assert conclusion_for("BLOCK", "required") == "failure"
    with pytest.raises(InputError, match="unknown verdict"):
        conclusion_for("UNKNOWN", "required")


def test_publish_uses_one_completed_exact_sha_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[Request] = []

    def opener(request: Request, timeout: float) -> _Response:
        assert timeout == 30.0
        requests.append(request)
        return _Response({"id": 73})

    monkeypatch.setattr(
        "aos_workflow_gate.github_decision_check.urllib.request.urlopen", opener
    )
    _set_context(monkeypatch)

    conclusion, check_id = publish_check(
        repository="owner/repo",
        sha=SHA,
        token="secret-token",
        api_url="https://api.github.com",
        mode="required",
        record=_record(),
    )

    assert (conclusion, check_id) == ("failure", 73)
    assert len(requests) == 1
    assert requests[0].method == "POST"
    body = _request_body(requests[0])
    assert body["name"] == CHECK_NAME
    assert body["head_sha"] == SHA
    assert body["status"] == "completed"
    assert body["conclusion"] == "failure"
    assert "/actions/runs/123/attempts/2" in body["details_url"]
    assert "**Problem:**" in body["output"]["summary"]
    assert "**Why it matters:**" in body["output"]["summary"]
    assert "**Next step:**" in body["output"]["summary"]
    assert "No source code was uploaded" in body["output"]["summary"]
    assert "secret-token" not in json.dumps(body)


def test_publish_requires_token_exact_sha_and_actions_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(InputError, match="checks: write"):
        publish_check(
            repository="owner/repo",
            sha=SHA,
            token=None,
            api_url="https://api.github.com",
            mode="advisory",
            record=_record(),
        )
    with pytest.raises(InputError, match="exact 40-character"):
        publish_check(
            repository="owner/repo",
            sha="main",
            token="token",
            api_url="https://api.github.com",
            mode="advisory",
            record=_record(),
        )
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ATTEMPT", raising=False)
    with pytest.raises(InputError, match="GITHUB_RUN_ID"):
        publish_check(
            repository="owner/repo",
            sha=SHA,
            token="token",
            api_url="https://api.github.com",
            mode="advisory",
            record=_record(),
        )


def test_reserved_decision_context_is_excluded_before_it_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules = [
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [
                    {"context": CHECK_NAME, "integration_id": APP_ID}
                ]
            },
        }
    ]
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setattr(
        requirements_module, "fetch_branch_rules", lambda *args, **kwargs: rules
    )
    monkeypatch.setattr(
        requirements_module,
        "fetch_classic_protection",
        lambda *args, **kwargs: {
            "protected": False,
            "details_available": True,
            "strict": False,
            "controls": [],
        },
    )
    monkeypatch.setattr(
        requirements_module,
        "fetch_check_runs",
        lambda *args, **kwargs: ([], False),
    )

    def wait(*args: Any, **kwargs: Any) -> tuple[list[Any], bool, list[Any], float]:
        assert kwargs["required_controls"] == []
        return [], False, [], 0.0

    monkeypatch.setattr(requirements_module, "wait_for_required", wait)
    monkeypatch.setattr(
        requirements_module,
        "fetch_commit_statuses",
        lambda *args, **kwargs: [],
    )

    snapshot = requirements_module.requirement_snapshot(
        api_url="https://api.github.com",
        slug="owner/repo",
        repository="owner/repo",
        sha=SHA,
        branch="main",
        token="token",
        budget=Budget(),
        exclude_self=True,
        exclude_control_contexts={CHECK_NAME},
    )

    assert snapshot["required_ids"] == []
    assert snapshot["self_reference_excluded"] == [CHECK_NAME]
    assert snapshot["controls"][0]["state"] == "self_reference"
    assert snapshot["incomplete_required"] == []


def test_cli_collects_before_publishing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    monkeypatch.chdir(tmp_path)
    _set_context(monkeypatch)

    def core(args: Any) -> int:
        events.append("collect")
        Path(args.out).write_text(
            json.dumps(_record()), encoding="utf-8"
        )
        return 0

    def publish(**kwargs: Any) -> tuple[str, int]:
        events.append("publish")
        return "neutral", 7

    monkeypatch.setattr(cli, "_cmd_run_core", core)
    monkeypatch.setattr(cli, "publish_check", publish)
    assert cli.main(["run", "--github-context", "--publish-check"]) == 0
    assert events == ["collect", "publish"]


def test_advisory_publish_failure_keeps_decision(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    _set_context(monkeypatch)

    def core(args: Any) -> int:
        Path(args.out).write_text(json.dumps(_record()), encoding="utf-8")
        return 0

    def fail(**kwargs: Any) -> tuple[str, int]:
        raise InputError("write permission unavailable")

    monkeypatch.setattr(cli, "_cmd_run_core", core)
    monkeypatch.setattr(cli, "publish_check", fail)
    assert cli.main(["run", "--github-context", "--publish-check"]) == 0
    assert "published check unavailable" in capsys.readouterr().err


def test_required_publish_failure_is_operational_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _set_context(monkeypatch)

    def core(args: Any) -> int:
        Path(args.out).write_text(json.dumps(_record()), encoding="utf-8")
        return 0

    def fail(**kwargs: Any) -> tuple[str, int]:
        raise InputError("write permission unavailable")

    monkeypatch.setattr(cli, "_cmd_run_core", core)
    monkeypatch.setattr(cli, "publish_check", fail)
    assert (
        cli.main(
            [
                "run",
                "--github-context",
                "--publish-check",
                "--published-check-mode",
                "required",
            ]
        )
        == 2
    )
