"""Every committed decision record must replay exactly from its committed
bundle and policy. This is the repository's own evidence discipline applied
to itself."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aos_workflow_gate import canonical
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.evidence import build_record, verify_record
from aos_workflow_gate.policy import load_policy

ROOT = Path(__file__).resolve().parents[1]

# (bundle, policy, record) triples; PR-evidence excludes the no-checkout job
# by collection-time operator choice (it is skipped on pull requests by
# design and would otherwise read as an advisory warning).
FIXTURES = [
    (
        "examples/github-pr-signal-bundle.json",
        "policies/default.yml",
        "examples/gate-decision.json",
    ),
    (
        "examples/aos-kernel-signal-bundle.json",
        "policies/aos-kernel-release-surface.yml",
        "examples/aos-kernel-gate-decision.json",
    ),
    (
        "examples/green-but-incomplete-bundle.json",
        "examples/green-but-incomplete-policy.json",
        "examples/green-but-incomplete-record.json",
    ),
    (
        "examples/pr-evidence-bundle.json",
        "examples/pr-evidence-policy.json",
        "examples/pr-evidence-record.json",
    ),
    (
        "examples/check-pr-bundle.json",
        "examples/check-pr-policy.json",
        "examples/check-pr-record.json",
    ),
]


@pytest.mark.parametrize("bundle_path,policy_path,record_path", FIXTURES)
def test_committed_record_replays(
    bundle_path: str, policy_path: str, record_path: str
) -> None:
    bundle = json.loads((ROOT / bundle_path).read_text(encoding="utf-8"))
    policy = load_policy(ROOT / policy_path)
    committed = json.loads((ROOT / record_path).read_text(encoding="utf-8"))

    decision = evaluate(bundle, policy)
    fresh = build_record(
        decision,
        policy=policy,
        input_bundle_digest=canonical.digest(bundle),
        can_block=policy.mode == "blocking",
    )
    assert fresh == committed
    assert verify_record(committed)


def test_expected_verdicts() -> None:
    verdicts = {
        "examples/green-but-incomplete-record.json": "WARN",
        "examples/pr-evidence-record.json": "PASS",
    }
    for path, expected in verdicts.items():
        record = json.loads((ROOT / path).read_text(encoding="utf-8"))
        assert record["verdict"] == expected, path
