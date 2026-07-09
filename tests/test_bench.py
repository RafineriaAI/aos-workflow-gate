from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical, cli
from aos_workflow_gate.agent_action import compute_digests
from aos_workflow_gate.bench import load_case, verify_case
from aos_workflow_gate.errors import InputError
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.evidence import build_record
from aos_workflow_gate.policy import Policy

BASE = "1" * 40
HEAD = "2" * 40


def _action_doc() -> dict[str, Any]:
    return {
        "contract": "agent-action-v0",
        "repository": "octo/repo",
        "base_sha": BASE,
        "subject": {"repository": "octo/repo", "sha": HEAD},
        "intent": {"task": "fix flaky test"},
        "action": {"type": "propose_patch", "parameters": {"files": ["a.py"]}},
    }


def _policy() -> Policy:
    return Policy.from_dict(
        {
            "policy_id": "bench-test",
            "schema_version": "draft-0",
            "rules": {
                "missing_required_source": "BLOCK",
                "failed_required_source": "BLOCK",
                "malformed_input": "BLOCK",
                "advisory_warning": "WARN",
            },
            "required_sources": ["ci"],
            "advisory_sources": [],
        }
    )


def _write_case(tmp_path: Path, **case_overrides: Any) -> Path:
    case_dir = tmp_path / "case-0001"
    case_dir.mkdir(exist_ok=True)

    doc = _action_doc()
    (case_dir / "action.json").write_text(json.dumps(doc), encoding="utf-8")

    patch = b"--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-x\n+y\n"
    (case_dir / "changes.patch").write_bytes(patch)

    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "octo/repo", "sha": HEAD},
        "sources": [
            {"id": "ci", "kind": "github_check", "status": "success",
             "required": True}
        ],
    }
    (case_dir / "bundle.json").write_text(json.dumps(bundle), encoding="utf-8")

    policy = _policy()
    (case_dir / "policy.json").write_text(
        json.dumps(policy.normalized), encoding="utf-8"
    )
    decision = evaluate(bundle, policy)
    record = build_record(
        decision,
        policy=policy,
        input_bundle_digest=canonical.digest(bundle),
        can_block=True,
    )
    (case_dir / "gate-decision.json").write_text(
        json.dumps(record), encoding="utf-8"
    )

    case = {
        "contract": "benchmark-case-v0",
        "case_id": "case-0001",
        "task": {"description": "fix flaky test", "declared_at": "T0"},
        "acceptance_criteria": ["required check ci succeeds on the head"],
        "budget": {"wall_clock_minutes": 30},
        "base_state": {
            "repository": "octo/repo", "base_sha": BASE, "branch": "main",
        },
        "artifacts": {
            "action": "action.json",
            "patch": "changes.patch",
            "bundle": "bundle.json",
            "policy": "policy.json",
            "record": "gate-decision.json",
        },
        "bindings": {
            "action_digest": compute_digests(doc)["action"],
            "patch_digest": "sha256:" + hashlib.sha256(patch).hexdigest(),
            "record_digest": record["record_digest"],
        },
        "chronology": [
            {"event": "task_declared", "at": "2026-07-09T10:00:00Z"},
            {"event": "action_captured", "at": "2026-07-09T10:10:00Z"},
            {"event": "decision_evaluated", "at": "2026-07-09T10:20:00Z"},
        ],
        "attestation": {
            "operator": "maintainer",
            "statement": "artifacts captured in the declared order",
        },
    }
    case.update(case_overrides)
    (case_dir / "case.json").write_text(json.dumps(case), encoding="utf-8")
    return case_dir


def test_valid_case_verifies_offline(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_dir = _write_case(tmp_path)
    assert cli.main(["bench-verify", "--case", str(case_dir), "--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["ok"] is True
    for name in (
        "artifact_presence",
        "chronology_consistent",
        "action_document",
        "action_digest_binding",
        "action_base_binding",
        "patch_digest_binding",
        "record_integrity",
        "offline_replay",
        "subject_binding",
    ):
        assert name in report["verified"], name
    for name in (
        "chronology_truth",
        "patch_authorship",
        "git_ancestry",
        "operator_attestation",
    ):
        assert name in report["unverifiable"], name


def test_tampered_record_fails(tmp_path: Path) -> None:
    case_dir = _write_case(tmp_path)
    record_path = case_dir / "gate-decision.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["verdict"] = "PASS" if record["verdict"] != "PASS" else "WARN"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    report = verify_case(case_dir)
    assert report["ok"] is False
    assert "record_integrity" in report["failed"]


def test_patch_mutation_fails_binding(tmp_path: Path) -> None:
    case_dir = _write_case(tmp_path)
    (case_dir / "changes.patch").write_bytes(b"different bytes")
    report = verify_case(case_dir)
    assert "patch_digest_binding" in report["failed"]


def test_policy_swap_fails_policy_binding(tmp_path: Path) -> None:
    case_dir = _write_case(tmp_path)
    policy_path = case_dir / "policy.json"
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["required_sources"] = []
    policy["advisory_sources"] = ["ci"]
    policy_path.write_text(json.dumps(policy), encoding="utf-8")
    report = verify_case(case_dir)
    assert "policy_binding" in report["failed"]
    # the swapped policy also changes the derived decision
    assert "semantic_replay" in report["failed"]


def test_doctored_record_fails_semantic_replay(tmp_path: Path) -> None:
    from aos_workflow_gate import canonical as canonical_module

    case_dir = _write_case(tmp_path)
    record_path = case_dir / "gate-decision.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["verdict"] = "BLOCK"
    record["summary"] = "Gate BLOCK: doctored."
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    record["record_digest"] = canonical_module.digest(payload)
    record_path.write_text(json.dumps(record), encoding="utf-8")

    case_path = case_dir / "case.json"
    case = json.loads(case_path.read_text(encoding="utf-8"))
    case["bindings"]["record_digest"] = record["record_digest"]
    case_path.write_text(json.dumps(case), encoding="utf-8")

    report = verify_case(case_dir)
    # self-digest and bundle binding hold, but the decision does not
    # re-derive from the committed inputs
    assert "record_integrity" in report["verified"]
    assert "offline_replay" in report["verified"]
    assert "semantic_replay" in report["failed"]


def test_declared_baseline_is_reported_unverifiable(tmp_path: Path) -> None:
    case_dir = _write_case(
        tmp_path,
        baseline={"github_merge_ready": True, "declared_by": "operator"},
    )
    report = verify_case(case_dir)
    assert "github_baseline" in report["unverifiable"]
    assert report["ok"] is True


def test_bundle_swap_fails_offline_replay(tmp_path: Path) -> None:
    case_dir = _write_case(tmp_path)
    bundle_path = case_dir / "bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["sources"][0]["status"] = "failure"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    report = verify_case(case_dir)
    assert "offline_replay" in report["failed"]


def test_chronology_disorder_fails(tmp_path: Path) -> None:
    case_dir = _write_case(
        tmp_path,
        chronology=[
            {"event": "task_declared", "at": "2026-07-09T11:00:00Z"},
            {"event": "action_captured", "at": "2026-07-09T10:10:00Z"},
            {"event": "decision_evaluated", "at": "2026-07-09T10:20:00Z"},
        ],
    )
    report = verify_case(case_dir)
    assert "chronology_consistent" in report["failed"]
    # truth of the timestamps stays out of scope either way
    assert "chronology_truth" in report["unverifiable"]


def test_missing_artifact_fails_early(tmp_path: Path) -> None:
    case_dir = _write_case(tmp_path)
    (case_dir / "changes.patch").unlink()
    report = verify_case(case_dir)
    assert report["failed"] == ["artifact_presence"]
    assert len(report["checks"]) == 1


def test_malformed_case_is_operational_error(tmp_path: Path) -> None:
    case_dir = _write_case(tmp_path, acceptance_criteria=[])
    with pytest.raises(InputError, match="acceptance_criteria"):
        load_case(case_dir)
    assert cli.main(["bench-verify", "--case", str(case_dir)]) == 2


def test_artifact_traversal_rejected(tmp_path: Path) -> None:
    case_dir = _write_case(tmp_path)
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    case["artifacts"]["patch"] = "../evil.patch"
    (case_dir / "case.json").write_text(json.dumps(case), encoding="utf-8")
    with pytest.raises(InputError, match="inside the case"):
        load_case(case_dir)


def test_live_ancestry_probe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    case_dir = _write_case(tmp_path)

    class _FakeResponse:
        def __init__(self, status: str) -> None:
            self._status = status

        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"status": self._status}).encode("utf-8")

    from aos_workflow_gate import collect as collect_module

    monkeypatch.setattr(
        collect_module.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse("ahead"),
    )
    report = verify_case(case_dir, live=True)
    assert "git_ancestry" in report["verified"]

    monkeypatch.setattr(
        collect_module.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse("diverged"),
    )
    report = verify_case(case_dir, live=True)
    assert "git_ancestry" in report["failed"]


def test_human_rendering_shows_boundary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    case_dir = _write_case(tmp_path)
    assert cli.main(["bench-verify", "--case", str(case_dir)]) == 0
    out = capsys.readouterr().out
    assert "all checks hold" in out
    assert "unverifiable" in out
    assert "runs no agent" in out
