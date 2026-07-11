"""Workflow state and expected-run visibility.

A workflow that never started is invisible to a check-runs collector;
these tests pin the two-stream (check suites + workflow runs) visibility
report: exact-SHA scope, the pending/action_required/unavailable model,
suite-keyed deduplication (no double counting), truncation disclosure,
and the guarantee that visibility never grades — ``missing`` exists
only relative to an explicit expectation.
"""

from __future__ import annotations

import io
import json
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate.collect import Budget
from aos_workflow_gate.workflow_state import (
    _suite_state,
    collect_workflow_visibility,
    fetch_check_suites,
    fetch_workflow_runs,
    workflow_visibility,
)

SHA = "c" * 40
APP = 15368


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


# --- state model ----------------------------------------------------------


@pytest.mark.parametrize(
    "status,conclusion,state",
    [
        ("completed", "success", "completed"),
        ("completed", "failure", "completed"),
        ("completed", "action_required", "action_required"),
        ("waiting", None, "action_required"),
        ("action_required", None, "action_required"),
        ("queued", None, "pending"),
        ("in_progress", None, "pending"),
        ("pending", None, "pending"),
        (None, None, "pending"),
    ],
)
def test_suite_state_model(
    status: str | None, conclusion: str | None, state: str
) -> None:
    assert _suite_state(status, conclusion) == state


# --- join and deduplication -----------------------------------------------


def _suite(
    suite_id: int, status: str = "queued", conclusion: str | None = None
) -> dict[str, Any]:
    return {
        "id": suite_id,
        "status": status,
        "conclusion": conclusion,
        "app": {"id": APP, "slug": "github-actions"},
    }


def _wrun(
    run_id: int,
    suite_id: int,
    *,
    status: str = "queued",
    conclusion: str | None = None,
    name: str = "CI",
    head_sha: str = SHA,
) -> dict[str, Any]:
    return {
        "id": run_id,
        "check_suite_id": suite_id,
        "status": status,
        "conclusion": conclusion,
        "name": name,
        "event": "pull_request",
        "head_sha": head_sha,
    }


def test_no_double_counting_suite_and_run_are_one_unit() -> None:
    report = workflow_visibility(
        [_suite(1), _suite(2, "completed", "success")],
        [_wrun(10, 1, name="CI")],
    )
    assert report["units_total"] == 2
    assert report["states"] == {
        "completed": 1, "pending": 1, "action_required": 0,
    }
    assert len(report["not_started"]) == 1
    unit = report["not_started"][0]
    assert unit["check_suite_id"] == 1
    assert unit["workflow_name"] == "CI"
    assert unit["run_id"] == 10
    assert unit["source"] == "check_suites"


def test_run_without_listed_suite_counts_once() -> None:
    report = workflow_visibility([], [_wrun(10, 7), _wrun(11, 7)])
    assert report["units_total"] == 1
    assert report["not_started"][0]["source"] == "workflow_runs"


def test_waiting_run_escalates_suite_to_action_required() -> None:
    # the suite still says "queued" while the run says "waiting"
    # (deployment approval); the sharper lifecycle state wins
    report = workflow_visibility(
        [_suite(1, "queued")], [_wrun(10, 1, status="waiting")]
    )
    assert report["not_started"][0]["state"] == "action_required"
    assert report["states"]["action_required"] == 1


def test_completed_units_are_counted_not_itemized() -> None:
    report = workflow_visibility(
        [_suite(1, "completed", "success")], []
    )
    assert report["units_total"] == 1
    assert report["not_started"] == []
    assert report["states"]["completed"] == 1


def test_truncation_is_disclosed() -> None:
    report = workflow_visibility([_suite(1)], [], suites_truncated=True)
    assert report["truncated"] is True


# --- fetch: exact SHA, pagination, degradation ----------------------------


def test_workflow_runs_exact_sha_filter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_workflow_gate import collect as collect_module

    payload = {
        "total_count": 2,
        "workflow_runs": [
            _wrun(1, 1), _wrun(2, 2, head_sha="d" * 40),
        ],
    }
    monkeypatch.setattr(
        collect_module.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(payload),
    )
    runs, truncated = fetch_workflow_runs(
        "octo/repo", SHA, token=None, budget=Budget()
    )
    assert [run["id"] for run in runs] == [1]
    assert truncated is False


def test_check_suites_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    from aos_workflow_gate import collect as collect_module

    pages = {
        1: [_suite(i) for i in range(100)],
        2: [_suite(100)],
    }

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        page = int(request.full_url.rsplit("page=", 1)[1])
        return _FakeResponse(
            {"total_count": 101, "check_suites": pages.get(page, [])}
        )

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    suites, truncated = fetch_check_suites(
        "octo/repo", SHA, token=None, budget=Budget()
    )
    assert len(suites) == 101
    assert truncated is False


def test_unreadable_suites_degrade_to_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_workflow_gate import collect as collect_module

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        raise HTTPError(
            request.full_url, 403, "forbidden", Message(), io.BytesIO(b"")
        )

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    report = collect_workflow_visibility(
        "octo/repo", SHA, token=None, budget=Budget()
    )
    assert report["available"] is False
    assert "unavailable" in report


def test_unreadable_runs_stream_is_disclosed_on_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from aos_workflow_gate import collect as collect_module

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        if "/actions/runs" in request.full_url:
            raise HTTPError(
                request.full_url, 403, "forbidden", Message(), io.BytesIO(b"")
            )
        return _FakeResponse(
            {"total_count": 1, "check_suites": [_suite(1)]}
        )

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    report = collect_workflow_visibility(
        "octo/repo", SHA, token=None, budget=Budget()
    )
    assert report["available"] is True
    assert report["units_total"] == 1
    assert "workflow_runs_unavailable" in report


# --- end to end: evidence, never grading ----------------------------------


def _run_check(
    name: str, conclusion: str | None = "success"
) -> dict[str, Any]:
    return {
        "id": 1,
        "name": name,
        "head_sha": SHA,
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": "2026-07-10T00:00:00Z",
        "app": {"id": APP},
        "details_url": "https://github.com/octo/repo/actions/runs/111/job/9",
    }


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rules: Any,
    runs: list[dict[str, Any]],
    suites: list[dict[str, Any]],
    workflow_runs: list[dict[str, Any]],
) -> None:
    from aos_workflow_gate import collect as collect_module

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        if "/rules/branches/" in url:
            return _FakeResponse(rules)
        if "/check-suites" in url:
            return _FakeResponse(
                {"total_count": len(suites), "check_suites": suites}
            )
        if "/actions/runs" in url:
            return _FakeResponse(
                {
                    "total_count": len(workflow_runs),
                    "workflow_runs": workflow_runs,
                }
            )
        if "/branches/" in url:
            return _FakeResponse({"protected": False})
        if url.endswith("/status") or "/status?" in url:
            return _FakeResponse({"state": "success", "statuses": []})
        return _FakeResponse({"total_count": len(runs), "check_runs": runs})

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)


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


def test_not_started_workflow_is_visible_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An approval-gated workflow appears in the digest-anchored bundle
    and on stdout — and does not change the verdict, because nothing
    expected it explicitly."""
    _install(
        monkeypatch,
        rules=RULES,
        runs=[_run_check("ci")],
        suites=[
            _suite(1, "completed", "success"),
            _suite(2, "queued", None),
        ],
        workflow_runs=[
            _wrun(10, 2, status="waiting", name="Deploy Preview"),
        ],
    )
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    assert record["verdict"] == "PASS"
    visibility = bundle["collection"]["workflow_visibility"]
    assert visibility["available"] is True
    assert visibility["units_total"] == 2
    assert visibility["states"]["action_required"] == 1
    unit = visibility["not_started"][0]
    assert unit["workflow_name"] == "Deploy Preview"
    out = capsys.readouterr().out
    assert "have not started" in out
    assert "Deploy Preview" in out


def test_missing_needs_an_explicit_expectation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A not-started workflow alone never produces a missing
    classification: without branch rules or operator-required checks
    there is no expected_by, so nothing is 'missing' — only visible."""
    _install(
        monkeypatch,
        rules=[],
        runs=[_run_check("lint")],
        suites=[_suite(2, "queued", None)],
        workflow_runs=[_wrun(10, 2, name="CI")],
    )
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    rules_hit = {reason["rule"] for reason in record["reasons"]}
    assert "missing_required_source" not in rules_hit
    # honest WARN comes from requiring nothing, not from the queued unit
    assert record["verdict"] == "WARN"
    assert "no_required_sources" in rules_hit
    assert bundle["collection"]["workflow_visibility"]["units_total"] == 1


def test_expected_and_not_started_still_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the rules DO expect the check and its workflow never
    started, grading stays fail-closed (missing) and the visibility
    report explains why nothing ran."""
    _install(
        monkeypatch,
        rules=RULES,
        runs=[],  # no check runs at all
        suites=[_suite(2, "queued", None)],
        workflow_runs=[_wrun(10, 2, status="waiting", name="CI")],
    )
    rc = cli.main(
        ["run", "--github-context",
         # opt out of the default 120 s discovery stabilization wait:
         # the check will never complete in this recorded scenario
         "--wait-seconds", "0.1", "--poll-interval", "0.1",
         "--out", str(tmp_path / "record.json"),
         "--bundle-out", str(tmp_path / "bundle.json"),
         "--policy-out", str(tmp_path / "policy.json")]
    )
    record = json.loads((tmp_path / "record.json").read_text("utf-8"))
    bundle = json.loads((tmp_path / "bundle.json").read_text("utf-8"))
    assert rc == 0
    assert record["verdict"] == "BLOCK"
    reasons = {
        (reason["rule"], reason["source_id"])
        for reason in record["reasons"]
    }
    assert ("missing_required_source", "ci") in reasons
    requirements = {
        req["context"]: req
        for req in bundle["collection"]["requirements"]
    }
    # the explicit expectation is the branch rule
    assert requirements["ci"]["required_by"] == ["rulesets"]
    visibility = bundle["collection"]["workflow_visibility"]
    assert visibility["states"]["action_required"] == 1
