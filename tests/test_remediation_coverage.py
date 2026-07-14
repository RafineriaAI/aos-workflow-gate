"""Remediation coverage and state precision.

Every evaluator rule has one deterministic fallback. Operational states
with distinct operator actions have explicit machine codes and templates.
The diagnosis tests separately prove that display text is never parsed.
"""

from __future__ import annotations

import re
from pathlib import Path

from aos_workflow_gate.summarize import (
    GENERIC_REMEDIATIONS,
    REPAIR_HINTS,
    STATE_REMEDIATIONS,
)

ROOT = Path(__file__).resolve().parents[1]

EXPECTED_RULES = {
    "missing_required_source",
    "failed_required_source",
    "advisory_warning",
    "malformed_input",
    "no_required_sources",
    "incomplete_collection",
    "non_independent_evidence",
    "verifier_change_unavailable",
}
EXPECTED_STATES = {
    ("missing_required_source", "missing"),
    ("missing_required_source", "pending"),
    ("missing_required_source", "unverifiable"),
    ("failed_required_source", "failure"),
    ("failed_required_source", "cancelled"),
    ("failed_required_source", "timed_out"),
    ("failed_required_source", "skipped"),
    ("failed_required_source", "neutral"),
    ("failed_required_source", "action_required"),
    ("failed_required_source", "stale"),
    ("failed_required_source", "startup_failure"),
    ("failed_required_source", "tampered"),
    ("failed_required_source", "subject_mismatch"),
    ("failed_required_source", "bounded_duplicate"),
    ("failed_required_source", "freshness_unverified"),
    ("incomplete_collection", "wait_timeout"),
    ("incomplete_collection", "subject_mismatch"),
    ("incomplete_collection", "truncated"),
}


def _emitted_rules() -> set[str]:
    source = (ROOT / "aos_workflow_gate" / "evaluate.py").read_text(encoding="utf-8")
    rules = set(re.findall(r'Reason\(\s*"([a-z_]+)"', source))
    assert rules, "rule extraction found nothing - pattern drifted"
    return rules


def test_every_emitted_rule_has_exactly_one_fallback() -> None:
    assert _emitted_rules() == EXPECTED_RULES
    assert set(GENERIC_REMEDIATIONS) == EXPECTED_RULES
    assert REPAIR_HINTS == {
        rule: remediation.action for rule, remediation in GENERIC_REMEDIATIONS.items()
    }


def test_state_inventory_is_explicit() -> None:
    assert set(STATE_REMEDIATIONS) == EXPECTED_STATES


def test_remediation_codes_are_unique_and_actions_are_deterministic() -> None:
    specs = [
        *GENERIC_REMEDIATIONS.values(),
        *STATE_REMEDIATIONS.values(),
    ]
    codes = [spec.code for spec in specs]

    assert len(codes) == len(set(codes))
    for spec in specs:
        assert re.fullmatch(r"[a-z][a-z0-9_]+", spec.code), spec.code
        action = spec.action.format(source="ci")
        assert "{" not in action and "}" not in action, spec.code
        assert len(action) > 40, spec.code
