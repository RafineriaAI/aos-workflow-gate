"""Replay the committed adversarial verification-binding corpus."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical, cli

ROOT = Path(__file__).resolve().parents[1]
CASES = sorted(
    (ROOT / "benchmarks" / "adversarial" / "bindings").glob("*.json")
)

CLASSIFICATIONS = {
    "positive_control",
    "negative_control",
    "neutral_control",
}
MUTATIONS = {
    "none",
    "cross_subject_rebound",
    "observation_scope_mismatch",
    "invalid_embedded_manifest",
    "digest_only_record",
    "future_manifest_schema",
    "exact_subject_context",
    "invalid_context_digest",
    "incomplete_context_binding",
    "record_observation_scope_mismatch",
    "different_valid_manifest",
}
REQUIRED_MECHANISMS = {
    "record_subject_binding",
    "observation_scope",
    "verifier_manifest_binding",
    "backward_compatibility",
    "forward_compatibility",
    "context_snapshot_binding",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_reference(relative: str) -> dict[str, Any]:
    path = (ROOT / relative).resolve()
    assert path.is_relative_to(ROOT), relative
    assert path.is_file(), relative
    return _load(path)


def _redigest(record: dict[str, Any]) -> None:
    record.pop("record_digest", None)
    record["record_digest"] = canonical.digest(record)


def _materialize(
    case: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    base = case["base"]
    record = _load_reference(base["record"])
    bundle = _load_reference(base["bundle"])
    mutation = case["mutation"]

    if mutation == "cross_subject_rebound":
        bundle["subject"]["sha"] = "e" * 40
        record["input_bundle_digest"] = canonical.digest(bundle)
    elif mutation == "observation_scope_mismatch":
        bundle["collection"] = {
            "status": "complete",
            "observation_scope": {
                "repository": bundle["subject"]["repository"],
                "head_sha": "e" * 40,
            },
        }
        record["input_bundle_digest"] = canonical.digest(bundle)
    elif mutation in {
        "exact_subject_context",
        "invalid_context_digest",
        "incomplete_context_binding",
    }:
        snapshot = {
            "GITHUB_REPOSITORY": bundle["subject"]["repository"],
            "GITHUB_SHA": bundle["subject"]["sha"],
        }
        collection = {
            "status": "complete",
            "observation_scope": {
                "repository": bundle["subject"]["repository"],
                "head_sha": bundle["subject"]["sha"],
            },
            "context_snapshot": snapshot,
        }
        if mutation != "incomplete_context_binding":
            collection["context_digest"] = (
                "sha256:" + "0" * 64
                if mutation == "invalid_context_digest"
                else canonical.digest(snapshot)
            )
        bundle["collection"] = collection
        record["input_bundle_digest"] = canonical.digest(bundle)
    elif mutation == "record_observation_scope_mismatch":
        record["observation"] = {
            "status": "complete",
            "observation_scope": {
                "repository": record["subject"]["repository"],
                "head_sha": "e" * 40,
            },
        }
    elif mutation == "invalid_embedded_manifest":
        manifest = record["generator"]["verifier_manifest"]
        files = dict(manifest["files"])
        files[sorted(files)[0]] = "0" * 64
        manifest["files"] = files
    elif mutation == "different_valid_manifest":
        manifest = record["generator"]["verifier_manifest"]
        files = dict(manifest["files"])
        files[sorted(files)[0]] = "0" * 64
        manifest["files"] = files
        manifest["manifest_digest"] = canonical.digest(files)
        record["generator"]["verifier_manifest_digest"] = manifest[
            "manifest_digest"
        ]
    elif mutation == "digest_only_record":
        record["generator"].pop("verifier_manifest")
    elif mutation == "future_manifest_schema":
        record["generator"]["verifier_manifest"]["schema_version"] = (
            "verifier-manifest-v1"
        )
    elif mutation != "none":
        raise AssertionError(f"unsupported corpus mutation: {mutation}")

    if mutation != "none":
        _redigest(record)
    return record, bundle


@pytest.mark.parametrize(
    "case_path", CASES, ids=[path.stem for path in CASES]
)
def test_binding_case_replays(
    case_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = _load(case_path)
    record, bundle = _materialize(case)
    expected = case["expected"]

    if "binding_detail" in expected:
        valid, detail = cli._bundle_bindings(record, bundle)
        assert valid is False
        assert detail == expected["binding_detail"]

    payloads = {"record.json": record, "bundle.json": bundle}
    monkeypatch.setattr(
        cli,
        "_load_json",
        lambda path: copy.deepcopy(payloads[path]),
    )
    rc = cli.main(
        [
            "verify",
            "--input",
            "record.json",
            "--bundle",
            "bundle.json",
        ]
    )
    output = capsys.readouterr().out

    assert rc == expected["exit_code"], case["case_id"]
    for fragment in expected["output_contains"]:
        assert fragment in output, (case["case_id"], fragment, output)


def test_binding_corpus_taxonomy_and_coverage() -> None:
    assert len(CASES) >= 12
    cases = [_load(path) for path in CASES]
    assert {case["case_id"] for case in cases} == {
        path.stem for path in CASES
    }
    assert {case["classification"] for case in cases} == CLASSIFICATIONS
    assert {case["mutation"] for case in cases} == MUTATIONS
    assert {case["expected"]["outcome"] for case in cases} == {
        "ACCEPT",
        "REJECT",
        "ACCEPT_WITH_DISCLOSURE",
    }
    assert REQUIRED_MECHANISMS <= {
        case["mechanism"] for case in cases
    }
    for case in cases:
        for relative in case["base"].values():
            path = (ROOT / relative).resolve()
            assert path.is_relative_to(ROOT)
            assert path.is_file()
