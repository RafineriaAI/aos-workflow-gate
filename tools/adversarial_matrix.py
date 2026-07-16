"""Generate the deterministic adversarial coverage matrix."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "adversarial"
OUTPUT = CORPUS / "MATRIX.md"


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for path in sorted((CORPUS / "cases").glob("*.json")):
        case = _load(path)
        rows.append(
            {
                "case_id": case["case_id"],
                "surface": "decision",
                "classification": case["classification"],
                "mechanism": case["mechanism"],
                "outcome": case["expected"]["verdict"],
            }
        )
    for path in sorted((CORPUS / "bindings").glob("*.json")):
        case = _load(path)
        rows.append(
            {
                "case_id": case["case_id"],
                "surface": "verification",
                "classification": case["classification"],
                "mechanism": case["mechanism"],
                "outcome": case["expected"]["outcome"],
            }
        )
    return sorted(rows, key=lambda row: (row["surface"], row["case_id"]))


def render_markdown(rows: list[dict[str, str]]) -> str:
    counts = Counter(row["classification"] for row in rows)
    mechanisms = sorted({row["mechanism"] for row in rows})
    tick = chr(96)
    lines = [
        "# Adversarial regression coverage",
        "",
        "Generated deterministically from committed corpus metadata.",
        "Decision fixtures and verification mutations are synthetic",
        "regression controls. They are not production incidents, market",
        "evidence, or GitHub-baseline contrast rows.",
        "",
        "| Case | Surface | Classification | Mechanism | Expected |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {tick}{row['case_id']}{tick} | {row['surface']} | "
            f"{tick}{row['classification']}{tick} | "
            f"{tick}{row['mechanism']}{tick} | "
            f"**{row['outcome']}** |"
        )
    lines.extend(
        [
            "",
            "## Coverage summary",
            "",
            f"- Total cases: **{len(rows)}**",
            f"- Positive controls: **{counts['positive_control']}**",
            f"- Negative controls: **{counts['negative_control']}**",
            f"- Neutral controls: "
            f"**{counts['neutral_control']}**",
            f"- Mechanisms: **{len(mechanisms)}**",
            "",
            "Mechanisms: "
            + ", ".join(
                f"{tick}{mechanism}{tick}" for mechanism in mechanisms
            )
            + ".",
            "",
            "Expected outcomes are consumed only by the test harness. The",
            "product evaluator and verifier receive only materialized",
            "bundle, policy, record, and manifest inputs.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    rows = build_rows()
    OUTPUT.write_text(
        render_markdown(rows),
        encoding="utf-8",
        newline="\n",
    )
    print(f"adversarial matrix cases: {len(rows)}")


if __name__ == "__main__":
    main()
