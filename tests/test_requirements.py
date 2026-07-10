from __future__ import annotations

import json
from typing import Any

import pytest

from aos_workflow_gate.requirements import (
    classify_control,
    qualifying_runs,
    requirement_evidence,
    requirement_snapshot,
)

SHA = "9" * 40
APP = 15368


def _control(context: str = "ci", integration_id: int | None = APP) -> dict[str, Any]:
    return {"context": context, "integration_id": integration_id}


def _run(
    name: str = "ci",
    conclusion: str | None = "success",
    *,
    app_id: int | None = APP,
    status: str = "completed",
    completed_at: str = "2026-07-09T00:00:00Z",
) -> dict[str, Any]:
    run: dict[str, Any] = {
        "id": 1,
        "name": name,
        "head_sha": SHA,
        "status": status,
        "conclusion": conclusion,
        "completed_at": completed_at,
    }
    if app_id is not None:
        run["app"] = {"id": app_id}
    return run


def test_satisfied_and_failed_by_qualifying_run() -> None:
    assert classify_control(_control(), [_run()], [])["state"] == "satisfied"
    failed = classify_control(_control(), [_run(conclusion="failure")], [])
    assert failed["state"] == "failed"
    assert failed["observed"]["conclusion"] == "failure"
    assert failed["observed"]["app_id"] == APP


def test_missing_and_pending() -> None:
    assert classify_control(_control(), [], [])["state"] == "missing"
    pending = classify_control(
        _control(), [_run(conclusion=None, status="in_progress")], []
    )
    assert pending["state"] == "pending"


def test_app_bound_identity_rejects_imposter() -> None:
    imposter = _run(app_id=99999)
    classified = classify_control(_control(), [imposter], [])
    assert classified["state"] == "unverifiable"
    assert classified["observed"]["nonqualifying_app_ids"] == [99999]

    # a run with no app identity at all cannot prove the binding either
    anonymous = _run(app_id=None)
    assert classify_control(_control(), [anonymous], [])["state"] == (
        "unverifiable"
    )

    # both present: the qualifying run decides, the imposter is noted
    both = classify_control(_control(), [imposter, _run()], [])
    assert both["state"] == "satisfied"
    assert 99999 in both["observed"]["nonqualifying_app_ids"]


def test_unbound_control_accepts_any_app_and_legacy_status() -> None:
    unbound = _control(integration_id=None)
    assert classify_control(
        unbound, [_run(app_id=424242)], []
    )["state"] == "satisfied"
    assert classify_control(
        unbound, [], [{"context": "ci", "state": "success"}]
    )["state"] == "satisfied"
    assert classify_control(
        unbound, [], [{"context": "ci", "state": "pending"}]
    )["state"] == "pending"
    assert classify_control(
        unbound, [], [{"context": "ci", "state": "failure"}]
    )["state"] == "failed"


def test_legacy_status_cannot_prove_app_bound_requirement() -> None:
    classified = classify_control(
        _control(), [], [{"context": "ci", "state": "success"}]
    )
    assert classified["state"] == "unverifiable"
    assert classified["observed"]["legacy_status_cannot_prove_app"] is True


def test_qualifying_runs_drops_imposters_only_for_bound_contexts() -> None:
    controls = [_control("ci", APP), _control("lint", None)]
    runs = [
        _run("ci"),
        _run("ci", app_id=99999),
        _run("lint", app_id=99999),
        _run("other", app_id=1),
    ]
    kept = qualifying_runs(runs, controls)
    names_apps = [(r["name"], r["app"]["id"]) for r in kept]
    assert ("ci", APP) in names_apps
    assert ("ci", 99999) not in names_apps
    assert ("lint", 99999) in names_apps
    assert ("other", 1) in names_apps


def test_requirement_evidence_is_compact() -> None:
    controls = [
        dict(_control(), state="satisfied", observed={"app_id": APP}),
        dict(_control("build", None), state="missing", observed={}),
    ]
    evidence = requirement_evidence(controls)
    assert evidence == [
        {"context": "ci", "integration_id": APP, "state": "satisfied"},
        {"context": "build", "integration_id": None, "state": "missing"},
    ]


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_snapshot_end_to_end(monkeypatch: pytest.MonkeyPatch) -> None:
    from aos_workflow_gate import collect as collect_module

    rules = [
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [
                    {"context": "ci", "integration_id": APP},
                    {"context": "legacy-gate"},
                ]
            },
        }
    ]
    runs = [_run("ci"), _run("ci", app_id=777)]

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        if "/rules/branches/" in url:
            return _FakeResponse(rules)
        if url.endswith("/status"):
            return _FakeResponse(
                {"state": "pending",
                 "statuses": [{"context": "legacy-gate", "state": "pending"}]}
            )
        return _FakeResponse({"total_count": len(runs), "check_runs": runs})

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    from aos_workflow_gate.collect import Budget

    snapshot = requirement_snapshot(
        api_url="https://api.github.com",
        slug="octo/repo",
        repository="octo/repo",
        sha=SHA,
        branch="main",
        token=None,
        budget=Budget(),
    )
    states = {c["context"]: c["state"] for c in snapshot["controls"]}
    assert states == {"ci": "satisfied", "legacy-gate": "pending"}
    assert snapshot["rules_digest"].startswith("sha256:")
    # the imposter never reaches the bundleable run set
    assert [(r["name"], r["app"]["id"]) for r in snapshot["qualifying_runs"]] == [
        ("ci", APP)
    ]
