from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical, cli
from aos_workflow_gate.collect import github_context_snapshot
from aos_workflow_gate.manifest import verifier_manifest
from aos_workflow_gate.policy import load_policy

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "examples" / "github-pr-signal-bundle.json"
RECORD = ROOT / "examples" / "gate-decision.json"
POLICY = ROOT / "policies" / "default.yml"
SHA = "0123456789abcdef0123456789abcdef01234567"


def test_policy_digest_guard(tmp_path: Path) -> None:
    good = load_policy(POLICY).digest
    out = tmp_path / "r.json"
    assert (
        cli.main(
            ["evaluate", "--input", str(BUNDLE), "--policy", str(POLICY),
             "--out", str(out), "--policy-digest", good]
        )
        == 0
    )
    assert (
        cli.main(
            ["evaluate", "--input", str(BUNDLE), "--policy", str(POLICY),
             "--out", str(out), "--policy-digest", "sha256:" + "0" * 64]
        )
        == 2
    )


def _bundle_with_context(snapshot: dict[str, str], digest: str) -> dict[str, Any]:
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    bundle["collection"] = {
        "status": "complete",
        "context_snapshot": snapshot,
        "context_digest": digest,
    }
    return bundle


def test_context_digest_selfcheck(tmp_path: Path) -> None:
    snapshot = {"GITHUB_REPOSITORY": "owner/repo", "GITHUB_SHA": SHA}
    good = _bundle_with_context(snapshot, canonical.digest(snapshot))
    good_path = tmp_path / "good.json"
    good_path.write_text(json.dumps(good), encoding="utf-8")
    assert (
        cli.main(["evaluate", "--input", str(good_path), "--policy", str(POLICY)])
        == 0
    )

    tampered = _bundle_with_context(
        {"GITHUB_REPOSITORY": "evil/repo", "GITHUB_SHA": SHA},
        canonical.digest(snapshot),
    )
    bad_path = tmp_path / "bad.json"
    bad_path.write_text(json.dumps(tampered), encoding="utf-8")
    assert (
        cli.main(["evaluate", "--input", str(bad_path), "--policy", str(POLICY)])
        == 2
    )


def _write_bound_pair(
    tmp_path: Path,
    record: dict[str, Any],
    bundle: dict[str, Any],
) -> tuple[Path, Path]:
    record["input_bundle_digest"] = canonical.digest(bundle)
    record.pop("record_digest", None)
    record["record_digest"] = canonical.digest(record)
    record_path = tmp_path / "record.json"
    bundle_path = tmp_path / "bundle.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    return record_path, bundle_path


def test_verify_rejects_cross_subject_pair(tmp_path: Path) -> None:
    record = json.loads(RECORD.read_text("utf-8"))
    bundle = json.loads(BUNDLE.read_text("utf-8"))
    bundle["subject"]["sha"] = "f" * 40
    record_path, bundle_path = _write_bound_pair(tmp_path, record, bundle)

    assert cli.main(
        ["verify", "--input", str(record_path), "--bundle", str(bundle_path)]
    ) == 1


def test_verify_rejects_invalid_context_digest(tmp_path: Path) -> None:
    record = json.loads(RECORD.read_text("utf-8"))
    bundle = json.loads(BUNDLE.read_text("utf-8"))
    snapshot = {
        "GITHUB_REPOSITORY": bundle["subject"]["repository"],
        "GITHUB_SHA": bundle["subject"]["sha"],
    }
    bundle["collection"] = {
        "status": "complete",
        "context_snapshot": snapshot,
        "context_digest": "sha256:" + "0" * 64,
    }
    record_path, bundle_path = _write_bound_pair(tmp_path, record, bundle)

    assert cli.main(
        ["verify", "--input", str(record_path), "--bundle", str(bundle_path)]
    ) == 1


def test_verify_rejects_subject_scope_mismatch(tmp_path: Path) -> None:
    record = json.loads(RECORD.read_text("utf-8"))
    bundle = json.loads(BUNDLE.read_text("utf-8"))
    bundle["collection"] = {
        "status": "complete",
        "observation_scope": {
            "repository": bundle["subject"]["repository"],
            "head_sha": "f" * 40,
        },
    }
    record_path, bundle_path = _write_bound_pair(tmp_path, record, bundle)

    assert cli.main(
        ["verify", "--input", str(record_path), "--bundle", str(bundle_path)]
    ) == 1


def test_verify_rejects_malformed_embedded_manifest(tmp_path: Path) -> None:
    record = json.loads(RECORD.read_text("utf-8"))
    bundle = json.loads(BUNDLE.read_text("utf-8"))
    manifest = verifier_manifest()
    files = dict(manifest["files"])
    files["evaluate.py"] = "0" * 64
    manifest["files"] = files
    record["generator"]["verifier_manifest"] = manifest
    record["generator"]["verifier_manifest_digest"] = manifest[
        "manifest_digest"
    ]
    record_path, bundle_path = _write_bound_pair(tmp_path, record, bundle)

    assert cli.main(
        ["verify", "--input", str(record_path), "--bundle", str(bundle_path)]
    ) == 1


def test_github_context_match(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_REF", raising=False)

    assert (
        cli.main(
            ["evaluate", "--input", str(BUNDLE), "--policy", str(POLICY),
             "--github-context-match"]
        )
        == 0
    )

    monkeypatch.setenv("GITHUB_SHA", "f" * 40)
    assert (
        cli.main(
            ["evaluate", "--input", str(BUNDLE), "--policy", str(POLICY),
             "--github-context-match"]
        )
        == 2
    )


def test_token_never_leaks_into_artifacts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from aos_workflow_gate import collect as collect_module

    secret = "ghs_SECRETSECRETSECRETSECRET"
    monkeypatch.setenv("GITHUB_TOKEN", secret)

    class _FakeResponse:
        def __enter__(self) -> _FakeResponse:
            return self

        def __exit__(self, *args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {
                    "total_count": 1,
                    "check_runs": [
                        {
                            "id": 1,
                            "name": "ci",
                            "head_sha": SHA,
                            "status": "completed",
                            "conclusion": "success",
                            "completed_at": "2026-07-05T00:00:00Z",
                        }
                    ],
                }
            ).encode("utf-8")

    monkeypatch.setattr(
        collect_module.urllib.request,
        "urlopen",
        lambda request, timeout=None: _FakeResponse(),
    )
    bundle_path = tmp_path / "b.json"
    policy_path = tmp_path / "p.json"
    assert (
        cli.main(
            ["collect", "--repository", "owner/repo", "--sha", SHA,
             "--out", str(bundle_path), "--policy-out", str(policy_path)]
        )
        == 0
    )
    captured = capsys.readouterr()
    for artifact in (
        bundle_path.read_text(encoding="utf-8"),
        policy_path.read_text(encoding="utf-8"),
        captured.out,
        captured.err,
    ):
        assert secret not in artifact


def test_context_snapshot_only_identity_keys(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "ghs_secret")
    monkeypatch.setenv("MY_SECRET", "x")
    snapshot = github_context_snapshot()
    assert "GITHUB_REPOSITORY" in snapshot
    assert "GITHUB_TOKEN" not in snapshot
    assert "MY_SECRET" not in snapshot


def test_signal_source_flows_into_record(tmp_path: Path) -> None:
    bundle = json.loads(BUNDLE.read_text(encoding="utf-8"))
    bundle["sources"][0]["signal_source"] = "github_check_runs_api"
    bundle_path = tmp_path / "b.json"
    bundle_path.write_text(json.dumps(bundle), encoding="utf-8")
    out = tmp_path / "r.json"
    assert (
        cli.main(
            ["evaluate", "--input", str(bundle_path), "--policy", str(POLICY),
             "--out", str(out)]
        )
        == 0
    )
    record = json.loads(out.read_text(encoding="utf-8"))
    by_id = {i["id"]: i for i in record["inputs"]}
    assert by_id[bundle["sources"][0]["id"]]["signal_source"] == (
        "github_check_runs_api"
    )
    other = [i for i in record["inputs"] if i["id"] != bundle["sources"][0]["id"]]
    assert all(i["signal_source"] is None for i in other)
