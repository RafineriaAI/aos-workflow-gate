"""Remediation coverage closure.

Every reason rule the evaluator can emit must map to exactly one
concrete, deterministic remediation hint - derived from the structural
reason code, never improvised per run. This suite extracts the emitted
rule set mechanically from the evaluator source, so a new rule without
a hint fails CI the moment it is written.
"""

from __future__ import annotations

import re
from pathlib import Path

from aos_workflow_gate.summarize import REPAIR_HINTS

ROOT = Path(__file__).resolve().parents[1]


def _emitted_rules() -> set[str]:
    source = (ROOT / "aos_workflow_gate" / "evaluate.py").read_text(
        encoding="utf-8"
    )
    rules = set(re.findall(r'Reason\(\s*"([a-z_]+)"', source))
    assert rules, "rule extraction found nothing - pattern drifted"
    return rules


def test_every_emitted_rule_has_exactly_one_hint() -> None:
    emitted = _emitted_rules()
    missing = emitted - set(REPAIR_HINTS)
    assert not missing, f"rules without a remediation hint: {sorted(missing)}"


def test_hints_are_deterministic_and_actionable() -> None:
    for rule, hint in REPAIR_HINTS.items():
        assert isinstance(hint, str) and hint, rule
        # deterministic: a plain string, no runtime formatting slots
        assert "{" not in hint and "}" not in hint, rule
        # actionable: more than a restatement of the code
        assert len(hint) > 40, rule


def test_known_rule_inventory_is_explicit() -> None:
    """The inventory below is the reviewed remediation surface; a new
    emitted rule must be added here consciously, with its hint."""
    assert _emitted_rules() == {
        "missing_required_source",
        "failed_required_source",
        "advisory_warning",
        "malformed_input",
        "no_required_sources",
        "incomplete_collection",
        "non_independent_evidence",
        "verifier_change_unavailable",
    }
