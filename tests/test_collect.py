from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical, cli
from aos_workflow_gate.collect import (
    build_bundle,
    build_generated_policy,
    resolve_github_context,
)
from aos_workflow_gate.errors import InputError

SHA = "3c00cddf59ebd233cca4761785e20ad51ac9ed78"


def _run(
    name: str,
    conclusion: str | None = "success",
    *,
    run_id: int = 1,
    status: str = "completed",
    completed_at: str = "2026-07-04T16:46:38Z",
) -> dict[str, Any]:
    return {
        "id": run_id,
        "name": name,
        "head_sha": SHA,
        "status": status,
        "conclusion": conclusion,
        "completed_at": completed_at,
    }


def test_build_bundle_skips_running_and_excluded_and_dedupes() -> None:
    runs = [
        _run("ci / validate", run_id=1),
        _run("ci / validate", "failure", run_id=2, completed_at="2026-07-04T17:00:00Z"),
        _run("self-gate", None, run_id=3, status="in_progress", completed_at=""),
        _run("noisy-bot", run_id=4),
    ]
    bundle = build_bundle(
        runs, repository="owner/repo", sha=SHA, exclude=["noisy-bot"]
    )
    assert [s["id"] for s in bundle["sources"]] == ["ci / validate"]
    assert bundle["sources"][0]["status"] == "failure"


def test_build_bundle_digest_matches_case_study_recipe() -> None:
    run = _run("ci / validate", run_id=42)
    bundle = build_bundle([run], repository="owner/repo", sha=SHA)
    identity = {
        "check_run_id": 42,
        "name": "ci / validate",
        "head_sha": SHA,
        "status": "completed",
        "conclusion": "success",
        "completed_at": "2026-07-04T16:46:38Z",
    }
    assert bundle["sources"][0]["digest"] == canonical.digest(identity)


def test_build_bundle_preserves_non_success_conclusions() -> None:
    runs = [_run("scorecard", "skipped", run_id=5)]
    bundle = build_bundle(runs, repository="owner/repo", sha=SHA)
    assert bundle["sources"][0]["status"] == "skipped"


def test_generated_policy_lists_all_sources_and_validates_required() -> None:
    runs = [_run("a", run_id=1), _run("b", run_id=2)]
    bundle = build_bundle(runs, repository="owner/repo", sha=SHA)
    policy = build_generated_policy(bundle, required=["a"])
    assert policy["required_sources"] == ["a"]
    assert policy["advisory_sources"] == ["b"]
    with pytest.raises(InputError):
        build_generated_policy(bundle, required=["missing-check"])


def test_resolve_github_context_prefers_pr_head_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    event = {"pull_request": {"number": 7, "head": {"sha": "a" * 40}}}
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_SHA", "b" * 40)
    monkeypatch.setenv("GITHUB_REF", "refs/pull/7/merge")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    context = resolve_github_context()
    assert context["sha"] == "a" * 40
    assert context["pull_request"] == 7

    monkeypatch.delenv("GITHUB_REPOSITORY")
    with pytest.raises(InputError):
        resolve_github_context()


def test_cli_collect_then_evaluate_offline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runs = [
        _run("ci / validate", run_id=1),
        _run("scanner", "failure", run_id=2),
    ]
    monkeypatch.setattr(cli, "fetch_check_runs", lambda *a, **k: runs)
    bundle_path = tmp_path / "bundle.json"
    policy_path = tmp_path / "policy.json"
    assert (
        cli.main(
            [
                "collect",
                "--repository",
                "owner/repo",
                "--sha",
                SHA,
                "--require",
                "ci / validate",
                "--out",
                str(bundle_path),
                "--policy-out",
                str(policy_path),
            ]
        )
        == 0
    )

    record_path = tmp_path / "record.json"
    assert (
        cli.main(
            [
                "evaluate",
                "--input",
                str(bundle_path),
                "--policy",
                str(policy_path),
                "--out",
                str(record_path),
            ]
        )
        == 0
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["verdict"] == "WARN"
    assert record["policy"]["policy_id"] == "collected-advisory"
    reasons = {(r["rule"], r["source_id"]) for r in record["reasons"]}
    assert ("advisory_warning", "scanner") in reasons
    required_flags = {i["id"]: i["required"] for i in record["inputs"]}
    assert required_flags == {"ci / validate": True, "scanner": False}


def test_cli_collect_require_needs_policy_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cli, "fetch_check_runs", lambda *a, **k: [])
    result = cli.main(
        [
            "collect",
            "--repository",
            "owner/repo",
            "--sha",
            SHA,
            "--require",
            "x",
            "--out",
            str(tmp_path / "b.json"),
        ]
    )
    assert result == 2
