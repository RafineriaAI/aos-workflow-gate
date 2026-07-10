from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical, cli
from aos_workflow_gate.adapters import sarif_source, scorecard_source
from aos_workflow_gate.errors import InputError
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.policy import Policy
from aos_workflow_gate.source_contract import (
    load_external_sources,
    source_digest,
    validate_source_v0,
)

SHA = "d" * 40


def _identity(status: str = "success") -> dict[str, Any]:
    return {"tool": "ext", "findings": 2, "status": status}


def _ext_source(source_id: str = "ext.scan", status: str = "warning") -> dict[str, Any]:
    identity = _identity(status)
    return {
        "id": source_id,
        "kind": "scanner_summary",
        "status": status,
        "digest": source_digest(identity),
        "contract": "source-v0",
        "signal_source": "ext_adapter",
    }


def _policy(required: list[str], advisory: list[str]) -> Policy:
    return Policy.from_dict(
        {
            "policy_id": "test",
            "schema_version": "draft-0",
            "rules": {
                "missing_required_source": "BLOCK",
                "failed_required_source": "BLOCK",
                "malformed_input": "BLOCK",
                "advisory_warning": "WARN",
            },
            "required_sources": required,
            "advisory_sources": advisory,
        }
    )


def test_source_digest_enforces_identity_completeness() -> None:
    identity = _identity()
    assert source_digest(identity) == canonical.digest(identity)
    with pytest.raises(InputError, match="identity-completeness"):
        source_digest({"tool": "ext", "findings": 2})
    with pytest.raises(InputError, match="mapping"):
        source_digest("not a mapping")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "value",
    [float("nan"), float("inf"), float("-inf")],
    ids=["nan", "positive-infinity", "negative-infinity"],
)
def test_canonical_json_rejects_non_finite_floats(value: float) -> None:
    with pytest.raises(ValueError, match="Out of range float values"):
        canonical.canonical_json_bytes({"value": value})


@pytest.mark.parametrize(
    "identity",
    [
        {"status": "success", "score": 1.25},
        {"status": "success", "scores": [1.25]},
        {"status": "success", "result": {"score": 1.25}},
        {"status": "success", "score": float("nan")},
        {"status": "success", "score": float("inf")},
        {"status": "success", "score": float("-inf")},
    ],
    ids=[
        "direct-float",
        "list-float",
        "nested-float",
        "nan",
        "positive-infinity",
        "negative-infinity",
    ],
)
def test_identity_float_rejected_by_import_and_evaluate(
    identity: dict[str, Any], tmp_path: Path
) -> None:
    with pytest.raises(InputError, match="floats are not allowed"):
        source_digest(identity)

    source = dict(
        _ext_source(status="success"),
        identity=identity,
        digest="sha256:" + "0" * 64,
    )
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(InputError, match="floats are not allowed"):
        load_external_sources(str(source_path))

    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "o/r", "sha": SHA},
        "sources": [source],
    }
    decision = evaluate(bundle, _policy(required=["ext.scan"], advisory=[]))
    assert decision.verdict == "BLOCK"
    assert any(
        reason.rule == "malformed_input"
        and "floats are not allowed" in reason.detail
        for reason in decision.reasons
    )


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        ({"digest": "not-a-digest"}, "digest"),
        ({"summary": 42}, "summary"),
        ({"verdict": "PASS"}, "unknown field"),
    ],
    ids=["malformed-digest", "optional-type", "unknown-field"],
)
def test_source_v0_validation_error_is_shared_by_import_and_evaluate(
    changes: dict[str, Any], expected: str, tmp_path: Path
) -> None:
    source = dict(_ext_source(status="success"), **changes)
    source_path = tmp_path / "source.json"
    source_path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(InputError) as imported:
        load_external_sources(str(source_path))
    assert expected in str(imported.value)

    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "o/r", "sha": SHA},
        "sources": [source],
    }
    decision = evaluate(bundle, _policy(required=["ext.scan"], advisory=[]))
    assert decision.verdict == "BLOCK"
    reason = next(
        reason
        for reason in decision.reasons
        if reason.rule == "malformed_input"
    )
    assert reason.detail == str(imported.value).replace(
        str(source_path), "sources[0]", 1
    )


def test_legacy_draft_0_source_remains_compatible() -> None:
    source = {
        "id": "legacy.scan",
        "kind": "legacy",
        "status": "success",
        "digest": "legacy-digest",
        "required": True,
        "legacy_note": "retained",
    }
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "o/r", "sha": SHA},
        "sources": [source],
    }
    decision = evaluate(bundle, _policy(required=["legacy.scan"], advisory=[]))
    assert decision.verdict == "PASS"


def test_validate_source_v0_precise_errors() -> None:
    good = validate_source_v0(_ext_source())
    assert good["contract"] == "source-v0"

    with pytest.raises(InputError, match=r"sources\[2\]: must be a JSON"):
        validate_source_v0("nope", where="sources[2]")
    with pytest.raises(InputError, match=r"x\.id: must be a non-empty"):
        validate_source_v0(dict(_ext_source(), id=""), where="x")
    with pytest.raises(InputError, match=r"x\.digest: must match sha256:"):
        validate_source_v0(dict(_ext_source(), digest="sha256:short"), where="x")
    with pytest.raises(InputError, match="unknown contract"):
        validate_source_v0(dict(_ext_source(), contract="source-v9"))
    with pytest.raises(InputError, match="unknown field"):
        validate_source_v0(dict(_ext_source(), verdict="PASS"))


def test_validate_source_v0_rejects_required_field() -> None:
    with pytest.raises(InputError, match="policy-owned"):
        validate_source_v0(dict(_ext_source(), required=True))


def test_identity_binding_recomputed_on_import_path() -> None:
    identity = _identity("warning")
    bound = dict(_ext_source(), identity=identity)
    assert validate_source_v0(bound)["identity"] == identity

    wrong_digest = dict(bound, digest="sha256:" + "0" * 64)
    with pytest.raises(InputError, match="identity binding violated"):
        validate_source_v0(wrong_digest)

    lying_status = dict(bound, status="success")
    with pytest.raises(InputError, match="does not match the"):
        validate_source_v0(lying_status)

    incomplete = dict(
        _ext_source(), identity={"tool": "ext", "findings": 2}
    )
    with pytest.raises(InputError, match="identity-completeness"):
        validate_source_v0(incomplete)


def test_identity_binding_fails_closed_in_evaluate() -> None:
    tampered = dict(
        _ext_source(), identity=dict(_identity("warning"), findings=999)
    )
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "o/r", "sha": SHA},
        "sources": [tampered],
    }
    decision = evaluate(bundle, _policy(required=[], advisory=["ext.scan"]))
    assert decision.verdict == "BLOCK"
    assert any(
        r.rule == "malformed_input" and "identity binding" in r.detail
        for r in decision.reasons
    )


def test_golden_digest_vectors_replay() -> None:
    from pathlib import Path

    vectors_path = (
        Path(__file__).resolve().parents[1]
        / "examples" / "digest-vectors.json"
    )
    doc = json.loads(vectors_path.read_text(encoding="utf-8"))
    assert doc["vectors"], "golden vector file must not be empty"
    for vector in doc["vectors"]:
        assert canonical.digest(vector["value"]) == vector["digest"], (
            vector["value"]
        )


def test_record_required_flags_are_policy_owned() -> None:
    # the bundle lies: required source claims false, advisory claims true
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "o/r", "sha": SHA},
        "sources": [
            {"id": "ci", "kind": "github_check", "status": "success",
             "required": False},
            {"id": "scan", "kind": "scanner_summary", "status": "warning",
             "required": True},
        ],
    }
    decision = evaluate(bundle, _policy(required=["ci"], advisory=["scan"]))
    by_id = {i["id"]: i for i in decision.inputs}
    assert by_id["ci"]["required"] is True  # policy wins over bundle
    assert by_id["scan"]["required"] is False
    assert decision.verdict == "WARN"


def test_source_v0_with_required_fails_closed() -> None:
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "o/r", "sha": SHA},
        "sources": [dict(_ext_source(), required=True)],
    }
    decision = evaluate(bundle, _policy(required=[], advisory=["ext.scan"]))
    assert decision.verdict == "BLOCK"
    assert any(
        r.rule == "malformed_input" and "policy-owned" in r.detail
        for r in decision.reasons
    )


def test_unknown_contract_fails_closed() -> None:
    bundle = {
        "schema_version": "draft-0",
        "subject": {"repository": "o/r", "sha": SHA},
        "sources": [dict(_ext_source(), contract="source-v9")],
    }
    decision = evaluate(bundle, _policy(required=[], advisory=[]))
    assert decision.verdict == "BLOCK"


def test_import_creates_fresh_bundle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    source_path = tmp_path / "ext.json"
    source_path.write_text(json.dumps(_ext_source()), encoding="utf-8")
    out = tmp_path / "bundle.json"
    assert (
        cli.main(
            ["import", "--source", str(source_path), "--repository", "o/r",
             "--sha", SHA, "--out", str(out)]
        )
        == 0
    )
    bundle = json.loads(out.read_text(encoding="utf-8"))
    assert bundle["subject"] == {"repository": "o/r", "sha": SHA}
    assert [s["id"] for s in bundle["sources"]] == ["ext.scan"]
    assert "required" not in bundle["sources"][0]
    assert bundle["collection"]["imported_sources"] == ["ext.scan"]
    assert "source-v0" in capsys.readouterr().out


def test_import_extends_bundle_and_rejects_collisions(tmp_path: Path) -> None:
    base = {
        "schema_version": "draft-0",
        "subject": {"repository": "o/r", "sha": SHA},
        "sources": [
            {"id": "ci", "kind": "github_check", "status": "success",
             "required": False}
        ],
    }
    base_path = tmp_path / "base.json"
    base_path.write_text(json.dumps(base), encoding="utf-8")
    source_path = tmp_path / "ext.json"
    source_path.write_text(
        json.dumps([_ext_source(), _ext_source("ext.other", "success")]),
        encoding="utf-8",
    )
    out = tmp_path / "merged.json"
    assert (
        cli.main(
            ["import", "--input", str(base_path), "--source",
             str(source_path), "--out", str(out)]
        )
        == 0
    )
    merged = json.loads(out.read_text(encoding="utf-8"))
    assert [s["id"] for s in merged["sources"]] == [
        "ci", "ext.other", "ext.scan"
    ]

    colliding = tmp_path / "collide.json"
    colliding.write_text(json.dumps(_ext_source("ci")), encoding="utf-8")
    assert (
        cli.main(
            ["import", "--input", str(out), "--source", str(colliding),
             "--out", str(out)]
        )
        == 2
    )


def test_import_reads_stdin(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps(_ext_source()))
    )
    out = tmp_path / "bundle.json"
    assert (
        cli.main(
            ["import", "--source", "-", "--repository", "o/r", "--sha", SHA,
             "--out", str(out)]
        )
        == 0
    )
    bundle = json.loads(out.read_text(encoding="utf-8"))
    assert bundle["sources"][0]["id"] == "ext.scan"


def test_import_error_is_path_addressed(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text(
        json.dumps([_ext_source(), {"id": "x", "kind": "k",
                                    "status": "s", "digest": "nope"}]),
        encoding="utf-8",
    )
    rc = cli.main(
        ["import", "--source", str(bad), "--repository", "o/r",
         "--sha", SHA, "--out", str(tmp_path / "b.json")]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "[1].digest" in err


def test_imported_bundle_evaluates_end_to_end(tmp_path: Path) -> None:
    source_path = tmp_path / "ext.json"
    source_path.write_text(json.dumps(_ext_source()), encoding="utf-8")
    bundle_path = tmp_path / "bundle.json"
    cli.main(
        ["import", "--source", str(source_path), "--repository", "o/r",
         "--sha", SHA, "--out", str(bundle_path)]
    )
    policy_path = tmp_path / "policy.json"
    policy_path.write_text(
        json.dumps(
            {
                "policy_id": "ext-test",
                "schema_version": "draft-0",
                "rules": {
                    "missing_required_source": "BLOCK",
                    "failed_required_source": "BLOCK",
                    "malformed_input": "BLOCK",
                    "advisory_warning": "WARN",
                },
                "required_sources": [],
                "advisory_sources": ["ext.scan"],
            }
        ),
        encoding="utf-8",
    )
    record_path = tmp_path / "record.json"
    assert (
        cli.main(
            ["evaluate", "--input", str(bundle_path), "--policy",
             str(policy_path), "--out", str(record_path)]
        )
        == 0
    )
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["verdict"] == "WARN"
    by_id = {i["id"]: i for i in record["inputs"]}
    assert by_id["ext.scan"]["required"] is False


def test_builtin_adapters_satisfy_identity_completeness(
    tmp_path: Path,
) -> None:
    sarif_path = tmp_path / "scan.sarif"
    sarif_path.write_text(
        json.dumps(
            {
                "version": "2.1.0",
                "runs": [
                    {
                        "tool": {"driver": {"name": "Demo", "version": "1"}},
                        "results": [{"level": "note"}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    sarif = sarif_source(sarif_path)
    identity = {
        "tool": "Demo",
        "version": "1",
        "error_count": 0,
        "warning_count": 0,
        "note_count": 1,
        "status": "warning",
    }
    assert sarif["digest"] == canonical.digest(identity)

    score_path = tmp_path / "score.json"
    score_path.write_text(
        json.dumps({"score": 9.0, "checks": [{}]}), encoding="utf-8"
    )
    scorecard = scorecard_source(score_path)
    assert scorecard["digest"] == canonical.digest(
        {"score": "9.0", "checks": 1, "status": "success"}
    )
