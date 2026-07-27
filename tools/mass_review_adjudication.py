"""Validate and aggregate final semantic labels for the review pain proxy."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from tools.mass_value_study import _canonical_digest, _load, _rate, _write

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT / "benchmarks" / "mass-market" / "review-adjudication-final-manifest.json"
)
DEFAULT_SOURCE = ROOT / "benchmarks" / "mass-market" / "review-proxy-final.json"
DEFAULT_LABELS = ROOT / "benchmarks" / "mass-market" / "review-adjudication-labels.json"
DEFAULT_OUT = ROOT / "benchmarks" / "mass-market" / "review-adjudication-final.json"
DEFAULT_REPORT = ROOT / "benchmarks" / "mass-market" / "REVIEW_ADJUDICATION_FINAL.md"


def _actionable_index(source: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result = {}
    for pull_request in source["pull_requests"]:
        for signal in pull_request["signals"]:
            if not signal["actionable_intervention_proxy"]:
                continue
            signal_id = str(signal["signal_instance_id"])
            result[signal_id] = {
                "category": signal["category"],
                "number": pull_request["number"],
                "repository": pull_request["repository"],
            }
    return result


def assess(
    manifest: dict[str, Any],
    source: dict[str, Any],
    labels_document: dict[str, Any],
) -> dict[str, Any]:
    if _canonical_digest(source) != manifest["source_result_digest"]:
        raise ValueError("source review proxy digest does not match manifest")
    index = _actionable_index(source)
    labels = labels_document.get("labels")
    if not isinstance(labels, list):
        raise ValueError("labels document has no labels")
    by_id = {
        str(label["signal_instance_id"]): label
        for label in labels
        if isinstance(label, dict)
    }
    if len(by_id) != len(labels):
        raise ValueError("labels contain duplicate or malformed signal IDs")
    if set(by_id) != set(index):
        missing = sorted(set(index) - set(by_id))
        unexpected = sorted(set(by_id) - set(index))
        raise ValueError(
            f"label set mismatch: missing={missing}, unexpected={unexpected}"
        )
    expected = int(manifest["expected_instances"])
    if len(labels) != expected:
        raise ValueError(f"received {len(labels)} labels, expected {expected}")

    category_valid = [label for label in labels if label["category_match_valid"]]
    true_directives = [
        label for label in labels if label["directive_validity"] == "true_directive"
    ]
    medium_high = [
        label for label in category_valid if label["severity"] in {"medium", "high"}
    ]
    business_relevant = [
        label
        for label in category_valid
        if label["business_relevance"] in {"material", "routine"}
    ]
    acceptance = [
        label
        for label in category_valid
        if label["acceptance_evidence"] != "insufficient"
    ]
    aligned = [label for label in category_valid if label["current_aos_alignment"]]

    def pr_ids(rows: list[dict[str, Any]]) -> set[tuple[str, int]]:
        return {
            (
                str(index[str(row["signal_instance_id"])]["repository"]),
                int(index[str(row["signal_instance_id"])]["number"]),
            )
            for row in rows
        }

    reviewed_prs = int(source["metrics"]["pull_requests_with_human_review"])
    valid_prs = pr_ids(category_valid)
    medium_high_prs = pr_ids(medium_high)
    metrics = {
        "acceptance_evidence_rate_among_category_valid": _rate(
            len(acceptance), len(category_valid)
        ),
        "adjudicated_actionable_pr_rate": _rate(len(valid_prs), reviewed_prs),
        "business_relevance_rate_among_category_valid": _rate(
            len(business_relevant), len(category_valid)
        ),
        "category_match_precision": _rate(len(category_valid), len(labels)),
        "category_valid_instances": len(category_valid),
        "current_aos_alignment_rate": _rate(len(aligned), len(category_valid)),
        "current_aos_aligned_instances": len(aligned),
        "labels": len(labels),
        "medium_or_high_pr_rate": _rate(len(medium_high_prs), reviewed_prs),
        "medium_or_high_rate_among_category_valid": _rate(
            len(medium_high), len(category_valid)
        ),
        "reviewed_pull_requests": reviewed_prs,
        "true_directive_rate": _rate(len(true_directives), len(labels)),
        "unique_category_valid_pull_requests": len(valid_prs),
        "unique_medium_or_high_pull_requests": len(medium_high_prs),
    }
    thresholds = manifest["thresholds"]
    checks = {
        "business_relevance": metrics["business_relevance_rate_among_category_valid"]
        >= thresholds["material_or_routine_business_relevance_rate_min"],
        "current_aos_alignment": metrics["current_aos_alignment_rate"]
        >= thresholds["current_aos_alignment_rate_min"],
        "medium_or_high": metrics["medium_or_high_rate_among_category_valid"]
        >= thresholds["medium_or_high_severity_rate_min"],
        "true_directive": metrics["true_directive_rate"]
        >= thresholds["true_directive_rate_min"],
    }
    return {
        "claim_boundary": manifest["claim_boundary"],
        "labels_digest": _canonical_digest(labels_document),
        "manifest_digest": _canonical_digest(manifest),
        "metrics": metrics,
        "schema_version": "aos-mass-review-adjudication-result/v0",
        "source_result_digest": _canonical_digest(source),
        "status": "ADJUDICATED_LOW_RATE_NO_CURRENT_AOS_ALIGNMENT",
        "study_id": manifest["study_id"],
        "threshold_checks": checks,
    }


def _pct(value: Any) -> str:
    return "n/a" if value is None else f"{100 * float(value):.1f}%"


def render(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    return "\n".join(
        [
            "# Final semantic adjudication",
            "",
            f"Status: `{result['status']}`.",
            "",
            "## Result",
            "",
            f"- Reviewed labels: **{metrics['labels']}**.",
            f"- True directive rate: **{_pct(metrics['true_directive_rate'])}**.",
            "- Category-match precision: "
            f"**{_pct(metrics['category_match_precision'])}**.",
            "- Medium/high among valid categories: "
            f"**{_pct(metrics['medium_or_high_rate_among_category_valid'])}**.",
            "- Material/routine among valid categories: "
            f"**{_pct(metrics['business_relevance_rate_among_category_valid'])}**.",
            "- Adjudicated actionable PRs: "
            f"**{metrics['unique_category_valid_pull_requests']}**/"
            f"**{metrics['reviewed_pull_requests']}** "
            f"({_pct(metrics['adjudicated_actionable_pr_rate'])}).",
            "- Medium/high PRs: "
            f"**{metrics['unique_medium_or_high_pull_requests']}**/"
            f"**{metrics['reviewed_pull_requests']}** "
            f"({_pct(metrics['medium_or_high_pr_rate'])}).",
            "- Current AOS alignment: "
            f"**{metrics['current_aos_aligned_instances']}**/"
            f"**{metrics['category_valid_instances']}** "
            f"({_pct(metrics['current_aos_alignment_rate'])}).",
            "",
            "## Boundary",
            "",
            str(result["claim_boundary"]),
            "The single evaluator was not independent or blinded. This result filters",
            "obvious lexical noise; it does not measure product usage or causality.",
            "",
            "## Integrity",
            "",
            f"- Manifest: `{result['manifest_digest']}`.",
            f"- Source: `{result['source_result_digest']}`.",
            f"- Labels: `{result['labels_digest']}`.",
            "",
        ]
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--labels", type=Path, default=DEFAULT_LABELS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = assess(_load(args.manifest), _load(args.source), _load(args.labels))
    _write(args.out, result)
    args.report.write_text(render(result), encoding="utf-8", newline="\n")
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
