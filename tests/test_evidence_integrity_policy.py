"""The second differentiating policy: evidence integrity in context.

``evidence-integrity`` proves value beyond required-status-check
control: it blocks on conditions no branch-protection rule can even
express — a collection that did not observe everything, evidence
produced by the change that is being judged, and a policy that requires
nothing. Data only: no new command surface, contract, or adapter.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from aos_workflow_gate.cli import resolve_policy_pack
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.policy import load_policy

ROOT = Path(__file__).resolve().parents[1]

SHA = "a" * 40
SUBJECT = {"repository": "octo/repo", "sha": SHA}


def _bundle(**collection: Any) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "schema_version": "draft-0",
        "subject": SUBJECT,
        "sources": [
            {"id": "ci", "kind": "github_check", "status": "success",
             "required": True}
        ],
    }
    if collection:
        bundle["collection"] = collection
    return bundle


def test_pack_resolves_and_is_blocking() -> None:
    policy = load_policy(resolve_policy_pack("evidence-integrity"))
    assert policy.mode == "blocking"
    assert policy.rules["incomplete_collection"] == "BLOCK"
    assert policy.rules["non_independent_evidence"] == "BLOCK"
    assert policy.rules["no_required_sources"] == "BLOCK"


def test_blocks_conditions_github_cannot_express() -> None:
    policy = load_policy(resolve_policy_pack("evidence-integrity"))

    # green checks, but the observation was incomplete
    incomplete = evaluate(_bundle(status="wait_timeout"), policy)
    assert incomplete.verdict == "BLOCK"
    assert any(
        r.rule == "incomplete_collection" for r in incomplete.reasons
    )

    # a complete, green observation passes
    clean = evaluate(_bundle(status="complete"), policy)
    assert clean.verdict == "PASS"


def test_differentiates_against_the_adversarial_corpus() -> None:
    """Under GitHub-required-checks logic the incomplete-collection case
    looks mergeable; the contextual policy blocks it."""
    case = json.loads(
        (
            ROOT / "benchmarks" / "adversarial" / "cases"
            / "incomplete-collection-clean.json"
        ).read_text(encoding="utf-8")
    )
    policy = load_policy(resolve_policy_pack("evidence-integrity"))
    decision = evaluate(case["bundle"], policy)
    assert decision.verdict == "BLOCK"
    assert any(
        r.rule == "incomplete_collection" for r in decision.reasons
    )
