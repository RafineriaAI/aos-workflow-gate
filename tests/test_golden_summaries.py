"""Golden summaries: the rendered summary text is a public surface.

Every committed example record renders to a committed golden Markdown
file, byte for byte. A wording change is then a reviewed diff, never an
accident. Regenerate deliberately with:

    AOS_UPDATE_GOLDEN=1 python -m pytest tests/test_golden_summaries.py
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aos_workflow_gate.summarize import diagnose, render_markdown

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"

CASES = (
    "gate-decision",
    "aos-kernel-gate-decision",
    "green-but-incomplete-record",
    "pr-evidence-record",
    "check-pr-record",
)


@pytest.mark.parametrize("name", CASES)
def test_summary_matches_golden(name: str) -> None:
    record = json.loads(
        (ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8")
    )
    text, intact = render_markdown(record)
    assert intact, f"{name} must verify before its summary is golden"
    golden_path = GOLDEN / f"{name}.md"
    if os.environ.get("AOS_UPDATE_GOLDEN") == "1":
        golden_path.parent.mkdir(parents=True, exist_ok=True)
        golden_path.write_text(text, encoding="utf-8", newline="\n")
    assert text == golden_path.read_text(encoding="utf-8"), (
        f"{name}: summary drifted from tests/golden/{name}.md; if the "
        "change is intentional, regenerate with AOS_UPDATE_GOLDEN=1"
    )


def test_summary_has_one_dominant_next() -> None:
    for name in CASES:
        record = json.loads(
            (ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8")
        )
        text, _ = render_markdown(record)
        next_lines = [
            line for line in text.splitlines()
            if line.startswith("**Next:**")
        ]
        assert len(next_lines) == 1, name
        assert "**Signals:**" in text, name


def test_diagnose_counts_are_consistent() -> None:
    record = json.loads(
        (ROOT / "examples" / "gate-decision.json").read_text(encoding="utf-8")
    )
    diag = diagnose(record)
    counts = diag["counts"]
    assert counts["required_total"] + counts["advisory_total"] == len(
        diag["inputs"]
    )
    assert counts["required_successful"] <= counts["required_total"]
    assert diag["next"], "the dominant next step must never be empty"
