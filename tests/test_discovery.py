from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate.checkpr import fetch_commit_statuses
from aos_workflow_gate.collect import Budget
from aos_workflow_gate.requirements import fetch_classic_protection

SHA = "c" * 40
APP = 15368
RUN_ID = "424242"


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _run(
    name: str,
    conclusion: str | None = "success",
    *,
    app_id: int | None = APP,
    status: str = "completed",
    self_run: bool = False,
) -> dict[str, Any]:
    run: dict[str, Any] = {
        "id": 1,
        "name": name,
        "head_sha": SHA,
        "status": status,
        "conclusion": conclusion,
        "completed_at": "2026-07-10T00:00:00Z",
        "details_url": (
            f"https://github.com/octo/repo/actions/runs/"
            f"{RUN_ID if self_run else '111'}/job/9"
        ),
    }
    if app_id is not None:
        run["app"] = {"id": app_id}
    return run


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rules: Any,
    runs: list[dict[str, Any]],
    branch_payload: Any = None,
    statuses: Any = None,
) -> None:
    from aos_workflow_gate import collect as collect_module

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        if "/rules/branches/" in url:
            if isinstance(rules, int):
                import io
                from email.message import Message
                from urllib.error import HTTPError

                raise HTTPError(url, rules, "x", Message(), io.BytesIO(b""))
            return _FakeResponse(rules)
        if "/branches/" in url:
            return _FakeResponse(branch_payload or {"protected": False})
        if url.endswith("/status") or "/status?" in url:
            return _FakeResponse(
                statuses
                if statuses is not None
                else {"state": "success", "statuses": []}
            )
        return _FakeResponse({"total_count": len(runs), "check_runs": runs})

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.setenv("GITHUB_RUN_ID", RUN_ID)
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_API_URL", raising=False)


RULES = [
    {
        "type": "required_status_checks",
        "parameters": {
            "required_status_checks": [{"context": "ci", "integration_id": APP}]
        },
    }
]


def _run_gate(tmp_path: Path) -> tuple[int, dict[str, Any], dict[str, Any]]:
    rc = cli.main(
        ["run", "--github-context",
         "--out", str(tmp_path / "record.json"),
         "--bundle-out", str(tmp_path / "bundle.json"),
         "--policy-out", str(tmp_path / "policy.json")]
    )
    record = json.loads((tmp_path / "record.json").read_text("utf-8"))
    bundle = json.loads((tmp_path / "bundle.json").read_text("utf-8"))
    return rc, record, bundle


def test_zero_config_discovers_ruleset_requirements(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install(monkeypatch, rules=RULES, runs=[_run("ci"), _run("lint")])
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    assert record["verdict"] == "PASS"
    requirements = {
        r["context"]: r["state"]
        for r in bundle["collection"]["requirements"]
    }
    assert requirements == {"ci": "satisfied"}
    assert bundle["collection"]["protection_source"] == "rulesets"
    by_id = {i["id"]: i for i in record["inputs"]}
    assert by_id["ci"]["required"] is True
    assert "Discovered 1 required status check(s) from rulesets" in (
        capsys.readouterr().out
    )


def test_discovery_enforces_app_bound_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, rules=RULES, runs=[_run("ci", app_id=666)])
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    assert record["verdict"] == "BLOCK"
    reasons = {(r["rule"], r["source_id"]) for r in record["reasons"]}
    assert ("missing_required_source", "ci") in reasons
    detail = next(
        r["detail"] for r in record["reasons"]
        if r["rule"] == "missing_required_source"
    )
    assert "requirement state: unverifiable" in detail


def test_discovery_falls_back_to_classic_protection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        rules=[],
        runs=[_run("legacy-ci", app_id=1)],
        branch_payload={
            "protected": True,
            "protection": {
                "required_status_checks": {
                    "checks": [{"context": "legacy-ci", "app_id": 1}]
                }
            },
        },
    )
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    assert record["verdict"] == "PASS"
    assert bundle["collection"]["protection_source"] == (
        "classic_branch_protection"
    )
    requirements = {
        r["context"]: r for r in bundle["collection"]["requirements"]
    }
    assert requirements["legacy-ci"]["integration_id"] == 1


def test_zero_required_all_green_is_warn_not_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, rules=[], runs=[_run("ci"), _run("lint")])
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    # every check green, nothing required: an honest WARN, never PASS
    assert record["verdict"] == "WARN"
    assert any(
        r["rule"] == "no_required_sources" for r in record["reasons"]
    )
    assert "requires nothing" in record["summary"]


def test_self_reference_is_excluded_and_recorded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rules = [
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [
                    {"context": "ci", "integration_id": APP},
                    {"context": "aos-gate", "integration_id": APP},
                ]
            },
        }
    ]
    runs = [
        _run("ci"),
        _run("aos-gate", None, status="in_progress", self_run=True),
    ]
    _install(monkeypatch, rules=rules, runs=runs)
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    assert record["verdict"] == "PASS"  # own check neither waits nor grades
    assert bundle["collection"]["self_reference_excluded"] == ["aos-gate"]
    requirements = {
        r["context"]: r["state"]
        for r in bundle["collection"]["requirements"]
    }
    assert requirements["aos-gate"] == "self_reference"
    assert "aos-gate" not in {s["id"] for s in bundle["sources"]}
    assert "Self-reference" in capsys.readouterr().out


def test_discovery_degrades_when_rules_unreadable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install(monkeypatch, rules=403, runs=[_run("ci")])
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    assert "can_continue: yes" in capsys.readouterr().err
    assert "requirements" not in bundle["collection"]
    # name-based zero-config still yields a decision (honest WARN here)
    assert record["verdict"] == "WARN"


def test_status_pagination_follows_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_workflow_gate import collect as collect_module

    pages = {
        1: [{"context": f"s{i}", "state": "success"} for i in range(100)],
        2: [{"context": "s100", "state": "success"}],
    }

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        page = 1
        if "page=" in url:
            page = int(url.rsplit("page=", 1)[1])
        return _FakeResponse(
            {"state": "success", "statuses": pages.get(page, [])}
        )

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    statuses = fetch_commit_statuses(
        "https://api.github.com", "octo/repo", SHA,
        token=None, budget=Budget(),
    )
    assert len(statuses) == 101


def test_classic_protection_details_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_workflow_gate import collect as collect_module

    monkeypatch.setattr(
        collect_module.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse({"protected": True}),
    )
    protected, controls, details = fetch_classic_protection(
        "https://api.github.com", "octo/repo", "main",
        token=None, budget=Budget(),
    )
    assert protected is True
    assert controls == []
    assert details is False
