from __future__ import annotations

import io
import json
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate.preflight import classify_response, run_preflight

SHA = "c" * 40
PR_URL = "https://github.com/octo/repo/pull/7"


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _headers(pairs: dict[str, str] | None = None) -> Message:
    message = Message()
    for key, value in (pairs or {}).items():
        message[key] = value
    return message


def _serve(spec: Any, url: str) -> _FakeResponse:
    if isinstance(spec, int):
        raise HTTPError(url, spec, f"HTTP {spec}", _headers(), io.BytesIO(b""))
    if isinstance(spec, tuple):
        code, headers = spec
        raise HTTPError(
            url, code, f"HTTP {code}", _headers(headers), io.BytesIO(b"")
        )
    if spec == "network":
        raise URLError("connection refused")
    return _FakeResponse(spec)


def _routes(**overrides: Any) -> dict[str, Any]:
    routes: dict[str, Any] = {
        "/rate_limit": {"resources": {"core": {"remaining": 4000}}},
        "repo": {"default_branch": "main", "private": False},
        "/pulls/": {"head": {"sha": SHA}, "base": {"ref": "main"}},
        "/check-runs": {"total_count": 2, "check_runs": []},
        "/status": {
            "state": "success",
            "statuses": [{"context": "ci", "state": "success"}],
        },
        "/rules/branches/": [
            {
                "type": "required_status_checks",
                "parameters": {
                    "required_status_checks": [{"context": "ci"}]
                },
            }
        ],
    }
    routes.update(overrides)
    return routes


def _install(monkeypatch: pytest.MonkeyPatch, routes: dict[str, Any]) -> None:
    from aos_workflow_gate import preflight as preflight_module

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        for key in (
            "/rate_limit",
            "/pulls/",
            "/check-runs",
            "/rules/branches/",
            "/status",
        ):
            if key in url:
                return _serve(routes[key], url)
        return _serve(routes["repo"], url)

    monkeypatch.setattr(
        preflight_module.urllib.request, "urlopen", opener
    )
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("AOS_GATE_WORKSPACE", raising=False)
    monkeypatch.delenv("GITHUB_API_URL", raising=False)


def test_classify_response_matrix() -> None:
    assert classify_response("repository", 200, rate_limited=False) is None
    cases = {
        401: "AOS-PERM-001",
        403: "AOS-PERM-002",
        404: "AOS-PERM-003",
        500: "AOS-ENV-002",
    }
    for status, code in cases.items():
        finding = classify_response("check_runs", status, rate_limited=False)
        assert finding is not None and finding["code"] == code
        assert finding["severity"] == "error"
    limited = classify_response("check_runs", 403, rate_limited=True)
    assert limited is not None and limited["code"] == "AOS-PERM-004"
    taxonomy = classify_response("check_runs", 403, rate_limited=False)
    assert taxonomy is not None and taxonomy["taxonomy"] == "permission"


def test_preflight_ready_end_to_end(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, _routes())
    assert cli.main(["preflight", "--pr", PR_URL, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["schema_version"] == "preflight-report-v0"
    assert report["ready"] is True
    assert report["scope"] == "operator"
    assert report["target"]["repository"] == "octo/repo"
    assert report["target"]["pull_request"] == 7
    by_cap = {p["capability"]: p for p in report["probes"]}
    for capability in (
        "rate_limit",
        "repository",
        "pull_request",
        "check_runs",
        "commit_statuses",
        "branch_rules",
    ):
        assert by_cap[capability]["status"] == "available"
    assert by_cap["branch_rules"]["observed"]["required_status_checks"] == 1
    # no token -> informational ENV-001, which must not degrade readiness
    codes = {f["code"] for f in report["findings"]}
    assert "AOS-ENV-001" in codes


def test_preflight_degraded_on_forbidden_checks(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, _routes(**{"/check-runs": 403}))
    assert cli.main(["preflight", "--pr", PR_URL]) == 1
    out = capsys.readouterr().out
    assert "degraded" in out
    assert "AOS-PERM-002" in out
    assert "checks: read" in out
    assert "remediation:" in out


def test_preflight_output_carries_no_verdict(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, _routes(**{"/check-runs": 403, "/status": 404}))
    cli.main(["preflight", "--pr", PR_URL, "--verbose"])
    out = capsys.readouterr().out
    for verdict in ("PASS", "WARN", "BLOCK"):
        assert verdict not in out


def test_preflight_feature_findings(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(
        monkeypatch,
        _routes(
            **{
                "/check-runs": {"total_count": 0, "check_runs": []},
                "/status": {"state": "pending", "statuses": []},
                "/rules/branches/": [],
            }
        ),
    )
    assert cli.main(["preflight", "--pr", PR_URL, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    codes = {f["code"] for f in report["findings"]}
    assert {"AOS-FEAT-001", "AOS-FEAT-002", "AOS-FEAT-003"} <= codes
    assert report["ready"] is True
    for finding in report["findings"]:
        if finding["code"].startswith("AOS-FEAT"):
            assert finding["taxonomy"] == "feature"
            assert finding["severity"] == "info"


def test_preflight_credentials_rejected_halts_probing(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, _routes(**{"/rate_limit": 401}))
    assert cli.main(["preflight", "--pr", PR_URL, "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    codes = [f["code"] for f in report["findings"]]
    assert codes.count("AOS-PERM-001") == 1  # named once, not per probe
    by_cap = {p["capability"]: p for p in report["probes"]}
    assert by_cap["repository"]["status"] == "skipped"
    assert by_cap["check_runs"]["status"] == "skipped"


def test_preflight_network_unreachable(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, _routes(**{"/rate_limit": "network"}))
    assert cli.main(["preflight", "--pr", PR_URL, "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    codes = {f["code"] for f in report["findings"]}
    assert "AOS-ENV-002" in codes
    by_cap = {p["capability"]: p for p in report["probes"]}
    assert by_cap["branch_rules"]["status"] == "skipped"


def test_preflight_low_rate_limit_warns_but_stays_ready(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(
        monkeypatch,
        _routes(**{"/rate_limit": {"resources": {"core": {"remaining": 3}}}}),
    )
    assert cli.main(["preflight", "--pr", PR_URL, "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    warned = [f for f in report["findings"] if f["code"] == "AOS-ENV-004"]
    assert warned and warned[0]["severity"] == "warn"
    assert report["ready"] is True


def test_preflight_workspace_boundary_invalid(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, _routes())
    monkeypatch.setenv("AOS_GATE_WORKSPACE", "Z:/does/not/exist-xyz")
    assert cli.main(["preflight", "--pr", PR_URL, "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    assert any(f["code"] == "AOS-ENV-003" for f in report["findings"])


def test_preflight_context_incomplete(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, _routes())
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    monkeypatch.delenv("GITHUB_SHA", raising=False)
    assert cli.main(["preflight", "--github-context", "--json"]) == 1
    report = json.loads(capsys.readouterr().out)
    findings = {f["code"]: f for f in report["findings"]}
    assert "AOS-CTX-001" in findings
    assert findings["AOS-CTX-001"]["taxonomy"] == "context"


def test_preflight_workflow_scope_resolves_context(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    _install(monkeypatch, _routes())
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    assert cli.main(["preflight", "--github-context", "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["scope"] == "workflow"
    assert report["target"]["repository"] == "octo/repo"
    assert report["target"]["sha"] == SHA


def test_preflight_without_target_is_operational_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert cli.main(["preflight"]) == 2
    err = capsys.readouterr().err
    assert "--github-context" in err


def test_token_never_leaks_into_report_or_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install(monkeypatch, _routes())
    secret = "ghs_PREFLIGHTSECRETSECRET"
    monkeypatch.setenv("GITHUB_TOKEN", secret)
    out = tmp_path / "preflight.json"
    assert (
        cli.main(["preflight", "--pr", PR_URL, "--json", "--out", str(out)])
        == 0
    )
    captured = capsys.readouterr()
    report_text = out.read_text(encoding="utf-8")
    for artifact in (report_text, captured.out, captured.err):
        assert secret not in artifact
    report = json.loads(report_text)
    assert report["token_present"] is True
    codes = {f["code"] for f in report["findings"]}
    assert "AOS-ENV-001" not in codes


def test_run_preflight_direct_requires_target() -> None:
    from aos_workflow_gate.errors import InputError

    with pytest.raises(InputError):
        run_preflight()
