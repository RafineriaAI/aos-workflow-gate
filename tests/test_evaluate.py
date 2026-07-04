from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import Policy, build_record, evaluate, load_policy, verify_record
from aos_workflow_gate.canonical import digest
from aos_workflow_gate.cli import main
from aos_workflow_gate.errors import InputError

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_BUNDLE = ROOT / "examples" / "github-pr-signal-bundle.json"
DEFAULT_POLICY = ROOT / "policies" / "default.yml"
DECISION_FIXTURE = ROOT / "examples" / "gate-decision.json"

SHA = "0123456789abcdef0123456789abcdef01234567"


def _example_bundle() -> dict[str, Any]:
    return json.loads(EXAMPLE_BUNDLE.read_text(encoding="utf-8"))


def _policy() -> Policy:
    return load_policy(DEFAULT_POLICY)


def _source(source_id: str, status: str, required: bool = False) -> dict[str, Any]:
    return {
        "id": source_id,
        "kind": "github_check",
        "status": status,
        "required": required,
    }


def _bundle(sources: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "draft-0",
        "subject": {
            "repository": "owner/repo",
            "ref": "refs/pull/1/merge",
            "sha": SHA,
            "pull_request": 1,
        },
        "sources": sources,
    }


def test_default_policy_parses_restricted_yaml() -> None:
    policy = _policy()
    assert policy.policy_id == "default"
    assert policy.mode == "advisory"
    assert policy.required_sources == ("ci.validate",)
    assert policy.advisory_sources == ("scanner.sarif", "agent.review")
    assert policy.rules["missing_required_source"] == "BLOCK"


def test_example_bundle_warns() -> None:
    decision = evaluate(_example_bundle(), _policy())
    assert decision.verdict == "WARN"
    assert any(r.rule == "advisory_warning" for r in decision.reasons)


def test_all_required_and_advisory_success_passes() -> None:
    bundle = _bundle(
        [
            _source("ci.validate", "success", required=True),
            _source("scanner.sarif", "success"),
            _source("agent.review", "success"),
        ]
    )
    assert evaluate(bundle, _policy()).verdict == "PASS"


def test_missing_required_source_blocks() -> None:
    decision = evaluate(_bundle([_source("scanner.sarif", "warning")]), _policy())
    assert decision.verdict == "BLOCK"
    assert any(r.rule == "missing_required_source" for r in decision.reasons)


def test_failed_required_source_blocks() -> None:
    decision = evaluate(
        _bundle([_source("ci.validate", "failure", required=True)]), _policy()
    )
    assert decision.verdict == "BLOCK"
    assert any(r.rule == "failed_required_source" for r in decision.reasons)


def test_missing_sha_blocks_when_required() -> None:
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "owner/repo"},
        "sources": [_source("ci.validate", "success", required=True)],
    }
    decision = evaluate(bundle, _policy())
    assert decision.verdict == "BLOCK"
    assert any(r.rule == "malformed_input" for r in decision.reasons)


def test_malformed_sources_block_and_record_verifies() -> None:
    policy = _policy()
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "owner/repo", "sha": SHA},
        "sources": "not-a-list",
    }
    decision = evaluate(bundle, policy)
    assert decision.verdict == "BLOCK"
    assert any(r.rule == "malformed_input" for r in decision.reasons)
    record = build_record(decision, policy=policy, input_bundle_digest=digest(bundle))
    assert verify_record(record)


def test_source_missing_id_blocks() -> None:
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "owner/repo", "sha": SHA},
        "sources": [{"kind": "github_check", "status": "success"}],
    }
    decision = evaluate(bundle, _policy())
    assert decision.verdict == "BLOCK"
    assert any(r.rule == "malformed_input" for r in decision.reasons)


def test_non_object_bundle_blocks() -> None:
    decision = evaluate(["not", "an", "object"], _policy())
    assert decision.verdict == "BLOCK"


def test_evaluation_is_deterministic() -> None:
    bundle = _example_bundle()
    policy = _policy()
    first = build_record(
        evaluate(bundle, policy), policy=policy, input_bundle_digest=digest(bundle)
    )
    second = build_record(
        evaluate(bundle, policy), policy=policy, input_bundle_digest=digest(bundle)
    )
    assert first == second
    assert first["record_digest"] == second["record_digest"]


def test_tamper_detection() -> None:
    bundle = _example_bundle()
    policy = _policy()
    record = build_record(
        evaluate(bundle, policy), policy=policy, input_bundle_digest=digest(bundle)
    )
    assert verify_record(record)
    tampered = dict(record)
    tampered["verdict"] = "PASS"
    assert not verify_record(tampered)


def test_input_bundle_digest_detects_mismatch() -> None:
    bundle = _example_bundle()
    policy = _policy()
    record = build_record(
        evaluate(bundle, policy), policy=policy, input_bundle_digest=digest(bundle)
    )
    assert record["input_bundle_digest"] == digest(bundle)
    other = _bundle([_source("ci.validate", "success", required=True)])
    assert record["input_bundle_digest"] != digest(other)


def test_json_and_yaml_policies_are_equivalent(tmp_path: Path) -> None:
    json_policy = {
        "schema_version": "draft-0",
        "policy_id": "default",
        "mode": "advisory",
        "verification_status": "UNSIGNED_NOT_OFFICIAL",
        "subject": {"require_repository": True, "require_sha": True},
        "rules": {
            "missing_required_source": "BLOCK",
            "failed_required_source": "BLOCK",
            "malformed_input": "BLOCK",
            "advisory_warning": "WARN",
        },
        "required_sources": ["ci.validate"],
        "advisory_sources": ["scanner.sarif", "agent.review"],
    }
    path = tmp_path / "default.json"
    path.write_text(json.dumps(json_policy), encoding="utf-8")
    assert load_policy(path).digest == _policy().digest


def test_invalid_policy_mode_raises(tmp_path: Path) -> None:
    path = tmp_path / "policy.yml"
    path.write_text(
        "policy_id: x\n"
        "mode: bogus\n"
        "rules:\n"
        "  missing_required_source: BLOCK\n"
        "  failed_required_source: BLOCK\n"
        "  malformed_input: BLOCK\n"
        "  advisory_warning: WARN\n",
        encoding="utf-8",
    )
    with pytest.raises(InputError):
        load_policy(path)


def test_cli_evaluate_writes_record(tmp_path: Path) -> None:
    out = tmp_path / "decision.json"
    code = main(
        [
            "evaluate",
            "--input",
            str(EXAMPLE_BUNDLE),
            "--policy",
            str(DEFAULT_POLICY),
            "--out",
            str(out),
        ]
    )
    assert code == 0
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["verdict"] == "WARN"
    assert verify_record(record)


def test_cli_enforce_returns_nonzero_on_block(tmp_path: Path) -> None:
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(
        json.dumps(_bundle([_source("scanner.sarif", "warning")])), encoding="utf-8"
    )
    code = main(
        [
            "evaluate",
            "--input",
            str(bundle_path),
            "--policy",
            str(DEFAULT_POLICY),
            "--enforce",
            "--out",
            str(tmp_path / "decision.json"),
        ]
    )
    assert code == 1


def test_cli_missing_input_returns_input_error_code(tmp_path: Path) -> None:
    code = main(
        [
            "evaluate",
            "--input",
            str(tmp_path / "does-not-exist.json"),
            "--policy",
            str(DEFAULT_POLICY),
        ]
    )
    assert code == 2


def test_committed_decision_fixture_is_replayable() -> None:
    bundle = _example_bundle()
    policy = _policy()
    record = build_record(
        evaluate(bundle, policy), policy=policy, input_bundle_digest=digest(bundle)
    )
    committed = json.loads(DECISION_FIXTURE.read_text(encoding="utf-8"))
    assert committed == record
    assert verify_record(committed)
