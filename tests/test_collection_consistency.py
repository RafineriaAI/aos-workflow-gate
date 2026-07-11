"""Collection consistency closure: one truth across entry points.

``run --github-context`` (zero-config discovery) and ``check-pr`` build
on the same requirement snapshot. This suite pins that fact end to end:
for one identical fake GitHub state, both commands must classify every
required control identically, agree on the rules digest, carry the same
workflow visibility evidence, and derive the same verdict. A divergence
here means two truths — the exact failure mode the shared snapshot
exists to prevent.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import cli

SHA = "d" * 40
APP = 15368

RULES = [
    {
        "type": "required_status_checks",
        "parameters": {
            "required_status_checks": [
                {"context": "ci", "integration_id": APP},
                {"context": "absent-control", "integration_id": APP},
            ]
        },
    }
]


def _run_payload(name: str, conclusion: str | None) -> dict[str, Any]:
    return {
        "id": 7,
        "name": name,
        "head_sha": SHA,
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": "2026-07-10T02:00:00Z",
        "details_url": "https://github.com/octo/repo/actions/runs/111/job/9",
        "app": {"id": APP},
        "check_suite": {"id": 501},
    }


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def _opener(request: Any, timeout: float | None = None) -> _FakeResponse:
    url = request.full_url
    if "/rules/branches/" in url:
        return _FakeResponse(RULES)
    if "/branches/" in url:
        return _FakeResponse({"protected": False})
    if "/pulls/" in url and "/files" not in url:
        return _FakeResponse(
            {
                "head": {"sha": SHA, "repo": {"full_name": "octo/repo"}},
                "base": {"ref": "main", "sha": "e" * 40,
                         "repo": {"full_name": "octo/repo"}},
                "state": "open",
                "merged": False,
                "draft": False,
            }
        )
    if "/files" in url:
        return _FakeResponse([])
    if "/status?" in url or url.endswith("/status"):
        return _FakeResponse({"state": "success", "statuses": []})
    if "/check-suites" in url:
        return _FakeResponse(
            {
                "total_count": 1,
                "check_suites": [
                    {"id": 501, "status": "completed",
                     "conclusion": "success", "app": {"id": APP}}
                ],
            }
        )
    if "/actions/runs" in url:
        return _FakeResponse({"total_count": 0, "workflow_runs": []})
    return _FakeResponse(
        {"total_count": 1, "check_runs": [_run_payload("ci", "success")]}
    )


def _requirements(bundle: dict[str, Any]) -> dict[str, str]:
    return {
        entry["context"]: entry["state"]
        for entry in bundle["collection"]["requirements"]
    }


def test_run_and_check_pr_agree_on_one_github_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from aos_workflow_gate import collect as collect_module

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", _opener)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_API_URL", raising=False)

    run_dir = tmp_path / "run"
    run_dir.mkdir()
    assert (
        cli.main(
            ["run", "--github-context", "--wait-seconds", "1",
             "--out", str(run_dir / "record.json"),
             "--bundle-out", str(run_dir / "bundle.json"),
             "--policy-out", str(run_dir / "policy.json")]
        )
        == 0
    )
    run_record = json.loads((run_dir / "record.json").read_text("utf-8"))
    run_bundle = json.loads((run_dir / "bundle.json").read_text("utf-8"))

    pr_dir = tmp_path / "checkpr"
    pr_dir.mkdir()
    monkeypatch.chdir(pr_dir)
    assert cli.main(["check-pr", "https://github.com/octo/repo/pull/9"]) == 0
    pr_record = json.loads((pr_dir / "gate-decision.json").read_text("utf-8"))
    pr_bundle = json.loads(
        (pr_dir / ".aos-gate" / "bundle.json").read_text("utf-8")
    )

    # one truth: identical classification of every required control
    assert _requirements(run_bundle) == _requirements(pr_bundle)
    assert _requirements(run_bundle) == {
        "ci": "satisfied",
        "absent-control": "missing",
    }
    assert (
        run_bundle["collection"]["rules_digest"]
        == pr_bundle["collection"]["rules_digest"]
    )
    for bundle in (run_bundle, pr_bundle):
        assert "workflow_visibility" in bundle["collection"]

    # both derive the same verdict from the same state (fail-closed on
    # the absent control) with the state named in the reason detail
    assert run_record["verdict"] == pr_record["verdict"] == "BLOCK"
    for record in (run_record, pr_record):
        detail = next(
            r["detail"] for r in record["reasons"]
            if r["rule"] == "missing_required_source"
            and r["source_id"] == "absent-control"
        )
        assert "requirement state: missing" in detail
