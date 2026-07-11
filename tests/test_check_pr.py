from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate.checkpr import (
    counterfactual_blockers,
    parse_pr_url,
    pending_required,
    required_checks_from_rules,
    rules_digest,
    status_sources,
    strict_policy_from_rules,
)
from aos_workflow_gate.errors import InputError

SHA = "b" * 40

RULES: list[dict[str, Any]] = [
    {"type": "deletion"},
    {"type": "pull_request", "parameters": {}},
    {
        "type": "required_status_checks",
        "parameters": {
            "required_status_checks": [
                {"context": "ci / validate", "integration_id": 15368},
                {"context": "build"},
            ]
        },
    },
]


def test_parse_pr_url_variants() -> None:
    coords = parse_pr_url("https://github.com/octo/repo/pull/42/files")
    assert coords["api_url"] == "https://api.github.com"
    assert coords["slug"] == "octo/repo"
    assert coords["repository"] == "octo/repo"
    assert coords["number"] == 42

    ghes = parse_pr_url("https://ghes.example.com/team/proj/pull/7")
    assert ghes["api_url"] == "https://ghes.example.com/api/v3"
    assert ghes["repository"] == "https://ghes.example.com/team/proj"

    for bad in (
        "http://github.com/o/r/pull/1",
        "https://github.com/o/r/issues/1",
        "https://github.com/o/r",
        "not a url",
    ):
        with pytest.raises(InputError):
            parse_pr_url(bad)


def test_required_checks_canonical_identity_and_drift() -> None:
    controls = required_checks_from_rules(RULES)
    assert controls == [
        {"context": "build", "integration_id": None},
        {"context": "ci / validate", "integration_id": 15368},
    ]
    assert rules_digest(RULES) == rules_digest(list(reversed(RULES)))
    assert rules_digest(RULES) != rules_digest(RULES[:2])


def test_counterfactual_blockers_only_nonrequired_failures() -> None:
    sources = [
        {"id": "a", "kind": "github_check", "required": True, "status": "failure"},
        {"id": "b", "kind": "github_check", "required": False, "status": "skipped"},
        {"id": "c", "kind": "github_check", "required": False, "status": "success"},
        {"id": "d", "kind": "branch_rules_summary", "required": False,
         "status": "skipped"},
        {"id": "e", "kind": "commit_status", "required": False,
         "status": "failure"},
    ]
    assert counterfactual_blockers(sources) == ["b", "e"]


def test_status_sources_mapping_and_precedence() -> None:
    statuses = [
        {"context": "jenkins/build", "state": "success"},
        {"context": "jenkins/deploy", "state": "error"},
        {"context": "ci / validate", "state": "success"},
        {"context": "jenkins/build", "state": "failure"},
        {"context": "slow/scan", "state": "pending"},
    ]
    sources, skipped = status_sources(
        statuses, exclude_contexts={"ci / validate"}
    )
    by_id = {s["id"]: s for s in sources}
    assert by_id["jenkins/build"]["status"] == "success"  # first wins
    assert by_id["jenkins/deploy"]["status"] == "failure"  # error -> failure
    assert by_id["slow/scan"]["status"] == "pending"
    assert skipped == ["ci / validate"]
    assert all(s["signal_source"] == "github_status_api" for s in sources)


def test_strict_and_pending_required() -> None:
    strict_rules: list[dict[str, Any]] = [
        {
            "type": "required_status_checks",
            "parameters": {
                "strict_required_status_checks_policy": True,
                "required_status_checks": [{"context": "ci"}],
            },
        }
    ]
    assert strict_policy_from_rules(strict_rules) is True
    assert strict_policy_from_rules(RULES) is False
    assert rules_digest(strict_rules) != rules_digest(
        [{**strict_rules[0], "parameters": {
            "strict_required_status_checks_policy": False,
            "required_status_checks": [{"context": "ci"}]}}]
    )

    raw_runs = [
        {"name": "ci", "status": "in_progress"},
        {"name": "other", "status": "in_progress"},
    ]
    status_srcs = [
        {"id": "jenkins/gate", "kind": "commit_status", "status": "pending"}
    ]
    assert pending_required(raw_runs, status_srcs, ["ci", "jenkins/gate"]) == [
        "ci", "jenkins/gate"
    ]


def _run(
    name: str, conclusion: str, app_id: int | None = 15368
) -> dict[str, Any]:
    run: dict[str, Any] = {
        "id": 1,
        "name": name,
        "head_sha": SHA,
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": "2026-07-05T00:00:00Z",
    }
    if app_id is not None:
        run["app"] = {"id": app_id}
    return run


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _fake_urlopen(runs: list[dict[str, Any]]):  # type: ignore[no-untyped-def]
    def opener(request, timeout=None):  # type: ignore[no-untyped-def]
        url = request.full_url
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
        if "/rules/branches/" in url:
            return _FakeResponse(RULES)
        if ("/status?" in url or url.endswith("/status")):
            return _FakeResponse(
                {
                    "state": "failure",
                    "statuses": [
                        {"context": "legacy/gate", "state": "failure"}
                    ],
                }
            )
        return _FakeResponse({"total_count": len(runs), "check_runs": runs})
    return opener


def test_check_pr_end_to_end_block_on_missing_required(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from aos_workflow_gate import collect as collect_module

    runs = [_run("ci / validate", "success"), _run("lint", "skipped")]
    monkeypatch.setattr(
        collect_module.urllib.request, "urlopen", _fake_urlopen(runs)
    )
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["check-pr", "https://github.com/octo/repo/pull/42"])
    assert rc == 0  # advisory observer never fails the process
    out = capsys.readouterr().out
    record = json.loads((tmp_path / "gate-decision.json").read_text("utf-8"))
    # 'build' is required by rules but never ran on head -> fail-closed BLOCK
    assert record["verdict"] == "BLOCK"
    assert record["can_block"] is False
    reasons = {(r["rule"], r["source_id"]) for r in record["reasons"]}
    assert ("missing_required_source", "build") in reasons
    bundle = json.loads(
        (tmp_path / ".aos-gate" / "bundle.json").read_text("utf-8")
    )
    assert bundle["collection"]["rules_digest"].startswith("sha256:")
    assert bundle["collection"]["counterfactual_blockers"] == [
        "legacy/gate", "lint"
    ]
    assert bundle["collection"]["pr"] == {
        "state": "open", "merged": False, "draft": False, "from_fork": False
    }
    assert bundle["collection"]["strict_up_to_date_required"] is False
    requirements = {
        req["context"]: req["state"]
        for req in bundle["collection"]["requirements"]
    }
    assert requirements == {"ci / validate": "satisfied", "build": "missing"}
    ids = {s["id"]: s for s in bundle["sources"]}
    assert ids["legacy/gate"]["kind"] == "commit_status"
    assert "Merge protection: 2 required status check(s)" in out
    assert "read-only observer" in out


def test_check_pr_imposter_app_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from aos_workflow_gate import collect as collect_module

    # 'ci / validate' is bound to app 15368; this run comes from app 666
    runs = [
        _run("ci / validate", "success", app_id=666),
        _run("build", "success"),
    ]
    monkeypatch.setattr(
        collect_module.urllib.request, "urlopen", _fake_urlopen(runs)
    )
    monkeypatch.chdir(tmp_path)
    assert cli.main(["check-pr", "https://github.com/octo/repo/pull/42"]) == 0
    out = capsys.readouterr().out
    record = json.loads((tmp_path / "gate-decision.json").read_text("utf-8"))
    assert record["verdict"] == "BLOCK"
    reasons = {(r["rule"], r["source_id"]) for r in record["reasons"]}
    assert ("missing_required_source", "ci / validate") in reasons
    bundle = json.loads(
        (tmp_path / ".aos-gate" / "bundle.json").read_text("utf-8")
    )
    assert bundle["collection"]["unverifiable_required"] == ["ci / validate"]
    requirements = {
        req["context"]: req["state"]
        for req in bundle["collection"]["requirements"]
    }
    assert requirements["ci / validate"] == "unverifiable"
    # the imposter run must not appear as a bundled source
    assert "ci / validate" not in {s["id"] for s in bundle["sources"]}
    assert "Unverifiable" in out
    assert "app-bound requirement" in out


def test_check_pr_enforce_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aos_workflow_gate import collect as collect_module

    runs = [_run("ci / validate", "failure"), _run("build", "success")]
    monkeypatch.setattr(
        collect_module.urllib.request, "urlopen", _fake_urlopen(runs)
    )
    monkeypatch.chdir(tmp_path)
    assert (
        cli.main(
            ["check-pr", "https://github.com/octo/repo/pull/42",
             "--mode", "enforce"]
        )
        == 1
    )
