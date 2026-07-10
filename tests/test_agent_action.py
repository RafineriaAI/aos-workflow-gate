from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate.agent_action import (
    classify_action,
    compute_digests,
    validate_action_document,
)
from aos_workflow_gate.errors import InputError

BASE = "e" * 40
HEAD = "f" * 40


def _doc(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "contract": "agent-action-v0",
        "repository": "octo/repo",
        "base_sha": BASE,
        "subject": {"repository": "octo/repo", "sha": HEAD},
        "intent": {"task": "fix flaky test", "declared_by": "operator"},
        "action": {
            "type": "propose_patch",
            "parameters": {"files": ["tests/test_x.py"], "lines": 12},
        },
        "snapshot": {"branch": "main", "head_sha": BASE},
        "agent": {"name": "any-agent", "version": "1.0"},
    }
    doc.update(overrides)
    return doc


def test_structural_validation_is_path_addressed() -> None:
    assert validate_action_document(_doc())["contract"] == "agent-action-v0"
    with pytest.raises(InputError, match=r"d\.contract"):
        validate_action_document(_doc(contract="other"), where="d")
    with pytest.raises(InputError, match=r"d\.base_sha.*40-character"):
        validate_action_document(_doc(base_sha="abc"), where="d")
    with pytest.raises(InputError, match=r"d\.subject\.sha"):
        validate_action_document(
            _doc(subject={"repository": "octo/repo", "sha": "x"}), where="d"
        )
    with pytest.raises(InputError, match=r"d\.intent\.task"):
        validate_action_document(_doc(intent={"note": "no task"}), where="d")
    with pytest.raises(InputError, match=r"d\.action\.parameters"):
        validate_action_document(
            _doc(action={"type": "t", "parameters": "not a mapping"}),
            where="d",
        )
    with pytest.raises(InputError, match=r"d\.digests\.bogus"):
        validate_action_document(
            _doc(digests={"bogus": "sha256:" + "0" * 64}), where="d"
        )


def test_digests_bind_intent_action_parameters_and_base() -> None:
    base = compute_digests(_doc())
    assert set(base) == {"intent", "parameters", "action", "snapshot"}
    for key, mutated in (
        ("intent", _doc(intent={"task": "other"})),
        ("parameters", _doc(action={"type": "propose_patch",
                                    "parameters": {"files": []}})),
        ("action", _doc(base_sha="a" * 40)),
    ):
        assert compute_digests(mutated)["action"] != base["action"], key
    # snapshot digest changes do not change the action digest
    assert (
        compute_digests(_doc(snapshot={"branch": "dev"}))["action"]
        == base["action"]
    )


def test_state_valid_and_freshness_unverified() -> None:
    state, explanation = classify_action(_doc())
    assert state == "freshness_unverified"
    assert "was not evaluated" in explanation
    assert "fails closed for required sources" in explanation

    state, explanation = classify_action(
        _doc(), observed_base=BASE, validation_mode="pinned"
    )
    assert state == "valid"
    assert "pinned staleness check passed" in explanation
    assert "no semantic approval" in explanation.lower()


def test_state_tampered_wins_over_everything() -> None:
    doc = _doc(digests={"intent": "sha256:" + "0" * 64})
    state, explanation = classify_action(
        doc,
        bundle_subject={"repository": "other/repo", "sha": "1" * 40},
        observed_base="2" * 40,
        validation_mode="pinned",
        seen_action_digests={compute_digests(doc)["action"]},
    )
    assert state == "tampered"
    assert "recomputed" in explanation


def test_state_subject_mismatch_before_stale() -> None:
    state, explanation = classify_action(
        _doc(),
        bundle_subject={"repository": "octo/repo", "sha": "1" * 40},
        observed_base="2" * 40,
        validation_mode="pinned",
    )
    assert state == "subject_mismatch"
    assert "does not match bundle" in explanation


def test_state_stale_and_bounded_duplicate() -> None:
    state, explanation = classify_action(
        _doc(), observed_base="2" * 40, validation_mode="live"
    )
    assert state == "stale"
    assert "has moved" in explanation

    digests = compute_digests(_doc())
    state, explanation = classify_action(
        _doc(),
        seen_action_digests={digests["action"]},
        duplicate_of="agent.action.first",
    )
    assert state == "bounded_duplicate"
    assert "no global duplicate or replay protection" in explanation


def test_cli_emits_source_v0_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from aos_workflow_gate import canonical

    doc_path = tmp_path / "action.json"
    doc_path.write_text(json.dumps(_doc()), encoding="utf-8")
    assert (
        cli.main(
            ["agent-action", "--input", str(doc_path), "--pinned-base", BASE]
        )
        == 0
    )
    captured = capsys.readouterr()
    sources = json.loads(captured.out)
    assert len(sources) == 1
    source = sources[0]
    assert source["kind"] == "agent_action"
    assert source["contract"] == "source-v0"
    assert source["status"] == "success"
    assert source["id"].startswith("agent.action.")
    assert "required" not in source
    assert ": success" in captured.err
    # identity binding: attached, consistent, and recomputable
    assert source["identity"]["status"] == source["status"]
    assert source["identity"]["duplicate_scope"] == "invocation+bundle"
    assert canonical.digest(source["identity"]) == source["digest"]


def test_cli_without_freshness_mode_is_freshness_unverified(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc_path = tmp_path / "action.json"
    doc_path.write_text(json.dumps(_doc()), encoding="utf-8")
    assert cli.main(["agent-action", "--input", str(doc_path)]) == 0
    sources = json.loads(capsys.readouterr().out)
    assert sources[0]["status"] == "freshness_unverified"
    assert "fails closed for required sources" in sources[0]["summary"]


def test_repository_subject_consistency_is_structural() -> None:
    doc = _doc(subject={"repository": "other/repo", "sha": HEAD})
    with pytest.raises(InputError, match="out of scope"):
        validate_action_document(doc, where="d")


def test_cli_duplicate_within_invocation_and_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc_path = tmp_path / "action.json"
    doc_path.write_text(json.dumps(_doc()), encoding="utf-8")
    assert (
        cli.main(
            ["agent-action", "--input", str(doc_path), "--input",
             str(doc_path), "--pinned-base", BASE]
        )
        == 0
    )
    sources = json.loads(capsys.readouterr().out)
    assert [s["status"] for s in sources] == ["success", "bounded_duplicate"]
    assert sources[1]["id"].endswith(".2")

    # merge the valid one into a bundle, then re-validate the same doc
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "octo/repo", "sha": HEAD},
        "sources": [sources[0]],
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    out = tmp_path / "merged.json"
    assert (
        cli.main(
            ["agent-action", "--input", str(doc_path), "--bundle",
             str(bundle_path), "--out", str(out), "--pinned-base", BASE]
        )
        == 0
    )
    merged = json.loads(out.read_text(encoding="utf-8"))
    statuses = [
        s["status"] for s in merged["sources"]
        if s["kind"] == "agent_action"
    ]
    assert sorted(statuses) == ["bounded_duplicate", "success"]


def test_cli_subject_mismatch_against_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc_path = tmp_path / "action.json"
    doc_path.write_text(json.dumps(_doc()), encoding="utf-8")
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "octo/repo", "sha": "3" * 40},
        "sources": [],
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    assert (
        cli.main(
            ["agent-action", "--input", str(doc_path), "--bundle",
             str(bundle_path)]
        )
        == 0
    )
    sources = json.loads(capsys.readouterr().out)
    assert sources[0]["status"] == "subject_mismatch"


def test_cli_pinned_stale_and_live_mode(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    doc_path = tmp_path / "action.json"
    doc_path.write_text(json.dumps(_doc()), encoding="utf-8")
    assert (
        cli.main(
            ["agent-action", "--input", str(doc_path), "--pinned-base",
             "9" * 40]
        )
        == 0
    )
    sources = json.loads(capsys.readouterr().out)
    assert sources[0]["status"] == "stale"

    class _FakeResponse:
        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({"commit": {"sha": BASE}}).encode("utf-8")

    from aos_workflow_gate import collect as collect_module

    monkeypatch.setattr(
        collect_module.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(),
    )
    assert (
        cli.main(["agent-action", "--input", str(doc_path), "--live"]) == 0
    )
    sources = json.loads(capsys.readouterr().out)
    assert sources[0]["status"] == "success"
    assert "live staleness check passed" in sources[0]["summary"]


def test_agent_source_flows_through_policy(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    doc_path = tmp_path / "action.json"
    doc_path.write_text(json.dumps(_doc()), encoding="utf-8")
    cli.main(
        ["agent-action", "--input", str(doc_path), "--pinned-base", BASE]
    )
    sources = json.loads(capsys.readouterr().out)
    source_id = sources[0]["id"]

    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "octo/repo", "sha": HEAD},
        "sources": sources,
    }
    bundle_path = tmp_path / "bundle.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

    def _policy(required: list[str]) -> Path:
        policy = {
            "policy_id": "agent-test",
            "schema_version": "draft-0",
            "rules": {
                "missing_required_source": "BLOCK",
                "failed_required_source": "BLOCK",
                "malformed_input": "BLOCK",
                "advisory_warning": "WARN",
            },
            "required_sources": required,
            "advisory_sources": (
                [] if required else [source_id]
            ),
        }
        path = tmp_path / "policy.json"
        path.write_text(json.dumps(policy), encoding="utf-8")
        return path

    # a valid agent action satisfies a policy that requires it
    record = tmp_path / "record.json"
    assert (
        cli.main(
            ["evaluate", "--input", str(bundle_path), "--policy",
             str(_policy([source_id])), "--out", str(record)]
        )
        == 0
    )
    assert json.loads(record.read_text("utf-8"))["verdict"] == "PASS"
    capsys.readouterr()  # drain the evaluate output

    # an unverified-freshness one fails closed when required
    cli.main(["agent-action", "--input", str(doc_path)])
    unverified = json.loads(capsys.readouterr().out)
    assert unverified[0]["status"] == "freshness_unverified"
    bundle["sources"] = unverified
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    cli.main(
        ["evaluate", "--input", str(bundle_path), "--policy",
         str(_policy([source_id])), "--out", str(record)]
    )
    blocked = json.loads(record.read_text("utf-8"))
    assert blocked["verdict"] == "BLOCK"
    assert any(
        r["rule"] == "failed_required_source" for r in blocked["reasons"]
    )

    # a source whose status disagrees with its identity is malformed
    lying = json.loads(json.dumps(sources[0]))
    lying["status"] = "stale"  # identity still says success
    bundle["sources"] = [lying]
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    cli.main(
        ["evaluate", "--input", str(bundle_path), "--policy",
         str(_policy([source_id])), "--out", str(record)]
    )
    malformed = json.loads(record.read_text("utf-8"))
    assert malformed["verdict"] == "BLOCK"
    assert any(
        r["rule"] == "malformed_input" and "identity" in r["detail"]
        for r in malformed["reasons"]
    )


def test_cli_rejects_conflicting_modes(tmp_path: Path) -> None:
    doc_path = tmp_path / "action.json"
    doc_path.write_text(json.dumps(_doc()), encoding="utf-8")
    assert (
        cli.main(
            ["agent-action", "--input", str(doc_path), "--live",
             "--pinned-base", "9" * 40]
        )
        == 2
    )
