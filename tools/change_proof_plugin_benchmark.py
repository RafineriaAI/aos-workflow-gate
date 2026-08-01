#!/usr/bin/env python3
"""Verify and summarize the exploratory Change Proof plug-in benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aos_workflow_gate import canonical  # noqa: E402
from aos_workflow_gate.evaluate import evaluate  # noqa: E402
from aos_workflow_gate.evidence import (  # noqa: E402
    build_record,
    observation_from_bundle,
    verify_record,
)
from aos_workflow_gate.policy import load_policy  # noqa: E402

DEFAULT_STUDY = ROOT / "benchmarks" / "change-proof-plugin"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-root", type=Path, default=DEFAULT_STUDY)
    parser.add_argument("--check", action="store_true")
    return parser


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _rate(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": round(numerator / denominator, 4) if denominator else None,
    }


def _analyze_case(study_root: Path, selected: dict[str, Any]) -> dict[str, Any]:
    case_id = str(selected["case_id"])
    case_root = study_root / str(selected["artifact_dir"])
    paths = {
        name: case_root / filename
        for name, filename in {
            "bundle": "bundle.json",
            "policy": "policy.json",
            "record": "gate-decision.json",
            "source": "source.json",
        }.items()
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise ValueError(f"{case_id}: missing artifacts: {', '.join(missing)}")

    bundle = _read_json(paths["bundle"])
    policy = _read_json(paths["policy"])
    record = _read_json(paths["record"])
    source = _read_json(paths["source"])
    loaded_policy = load_policy(paths["policy"])
    replayed = build_record(
        evaluate(bundle, loaded_policy),
        policy=loaded_policy,
        input_bundle_digest=canonical.digest(bundle),
        can_block=bool(record.get("can_block")),
        observation=observation_from_bundle(bundle),
    )

    source_identity = _dict(source.get("identity"))
    bundle_sources = bundle.get("sources")
    source_in_bundle = (
        isinstance(bundle_sources, list)
        and len(bundle_sources) == 1
        and bundle_sources[0] == source
    )
    record_policy = _dict(record.get("policy"))
    integrity = {
        "record_digest": verify_record(record),
        "bundle_digest": record.get("input_bundle_digest")
        == canonical.digest(bundle),
        "policy_digest": record_policy.get("digest") == canonical.digest(policy),
        "semantic_replay": replayed == record,
        "standalone_source_binding": source_in_bundle,
        "exact_subject": (
            source_identity.get("repository") == selected["repository"]
            and source_identity.get("head_sha") == selected["head_sha"]
            and source_identity.get("base_sha") == selected["base_sha"]
        ),
    }

    head_runs = source_identity.get("head_runs")
    challenge_runs = source_identity.get("challenge_runs")
    if not isinstance(head_runs, list) or not isinstance(challenge_runs, list):
        raise ValueError(f"{case_id}: run observations are missing")
    head_ms = sum(int(_dict(run).get("elapsed_ms", 0)) for run in head_runs)
    challenge_ms = sum(
        int(_dict(run).get("elapsed_ms", 0)) for run in challenge_runs
    )
    verifier_total_ms = head_ms + challenge_ms
    raw_verdict = record.get("verdict")

    return {
        **selected,
        "raw_verdict": raw_verdict,
        "raw_status": source.get("status"),
        "implementation_paths": source_identity.get("implementation_paths"),
        "head_run_ms": head_ms,
        "challenge_runs_ms": challenge_ms,
        "verifier_total_ms": verifier_total_ms,
        "verifier_work_ratio": (
            round(verifier_total_ms / head_ms, 3) if head_ms else None
        ),
        "integrity": integrity,
        "integrity_ok": all(integrity.values()),
        "expected_raw_outcome": raw_verdict == selected["expected_raw_verdict"],
    }


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    code_and_tests = [
        case for case in cases if case["cohort"] == "observed_code_and_tests"
    ]
    preserving = [
        case
        for case in cases
        if case["cohort"] == "observed_behavior_preserving_control"
    ]
    controlled = [
        case
        for case in cases
        if case["cohort"] == "controlled_under_scoped_verifier"
    ]
    eligible = [case for case in cases if case["adaptive_action"] == "run"]
    skipped = [case for case in cases if case["adaptive_action"] == "skip"]
    ratios = [
        float(case["verifier_work_ratio"])
        for case in cases
        if case["verifier_work_ratio"] is not None
    ]
    return {
        "cases": len(cases),
        "repositories": len({str(case["repository"]) for case in cases}),
        "raw_verdicts": dict(Counter(str(case["raw_verdict"]) for case in cases)),
        "integrity": _rate(sum(case["integrity_ok"] for case in cases), len(cases)),
        "expected_raw_outcomes": _rate(
            sum(case["expected_raw_outcome"] for case in cases), len(cases)
        ),
        "observed_code_and_tests_distinguished": _rate(
            sum(case["raw_verdict"] == "PASS" for case in code_and_tests),
            len(code_and_tests),
        ),
        "behavior_preserving_raw_warnings": _rate(
            sum(case["raw_verdict"] == "WARN" for case in preserving),
            len(preserving),
        ),
        "controlled_under_scoped_detected": _rate(
            sum(case["raw_verdict"] == "WARN" for case in controlled),
            len(controlled),
        ),
        "adaptive_eligible": len(eligible),
        "adaptive_skipped": len(skipped),
        "noisy_recommendations_avoided_by_scope": _rate(
            sum(
                case["value_interpretation"] == "noisy_if_run_by_default"
                for case in skipped
            ),
            len(skipped),
        ),
        "median_head_run_seconds": round(
            median(float(case["head_run_ms"]) for case in cases) / 1000, 3
        ),
        "median_verifier_total_seconds": round(
            median(float(case["verifier_total_ms"]) for case in cases) / 1000,
            3,
        ),
        "median_cli_wall_seconds": round(
            median(float(case["wall_seconds"]) for case in cases), 3
        ),
        "median_verifier_work_ratio": round(median(ratios), 3),
        "external_actionable_findings": 0,
        "external_decision_changes": 0,
    }


def analyze(study_root: Path) -> dict[str, Any]:
    manifest = _read_json(study_root / "manifest.json")
    selection = _read_json(study_root / "selection.json")
    selected_cases = selection.get("cases")
    if not isinstance(selected_cases, list):
        raise ValueError("selection.cases must be a list")
    cases = [
        _analyze_case(study_root, selected)
        for selected in selected_cases
        if isinstance(selected, dict)
    ]
    metrics = _aggregate(cases)
    mechanism_ok = (
        metrics["integrity"]["rate"] == 1.0
        and metrics["expected_raw_outcomes"]["rate"] == 1.0
    )
    calibrated_ok = (
        metrics["observed_code_and_tests_distinguished"]["rate"] == 1.0
        and metrics["controlled_under_scoped_detected"]["rate"] == 1.0
        and metrics["noisy_recommendations_avoided_by_scope"]["rate"] == 1.0
    )
    return {
        "schema_version": "aos-change-proof-plugin-results/v0",
        "study_id": manifest["study_id"],
        "study_status": manifest["status"],
        "mechanism_result": "PASS" if mechanism_ok else "FAIL",
        "product_direction": (
            "CONTINUE_NARROW_PLUGIN_EXPERIMENT"
            if mechanism_ok and calibrated_ok
            else "STOP_OR_RECALIBRATE"
        ),
        "default_enablement": "DO_NOT_ENABLE_BY_DEFAULT",
        "roi_status": "UNPROVEN_REQUIRES_EXTERNAL_USE",
        "recommended_scope": manifest["candidate"]["default_scope"],
        "metrics": metrics,
        "cases": cases,
        "claim_boundary": manifest["claim_boundary"],
        "unmeasured_without_users": manifest["unmeasured_without_users"],
    }


def _fraction(metric: dict[str, Any]) -> str:
    return f"{metric['numerator']}/{metric['denominator']}"


def render_report(results: dict[str, Any]) -> str:
    metrics = results["metrics"]
    lines = [
        "# AOS as a plug-in to existing tests",
        "",
        "## Decision",
        "",
        f"- Direction: **{results['product_direction']}**",
        f"- Default enablement: **{results['default_enablement']}**",
        f"- ROI: **{results['roi_status']}**",
        "",
        "The strongest current product question is:",
        "",
        (
            "> The tests pass, but would they still pass without the "
            "implementation change?"
        ),
        "",
        "AOS should answer this as a plug-in after an existing targeted test command. "
        "It should not replace the test runner, coverage service, scanner, or "
        "reviewer.",
        "",
        "## What the experiment found",
        "",
        (
            "- Real merged pull requests that changed code and tests, where the "
            f"tests distinguished the implementation: "
            f"{_fraction(metrics['observed_code_and_tests_distinguished'])}."
        ),
        (
            "- Controlled run where the verifier omitted every changed test file, "
            f"and AOS warned: "
            f"{_fraction(metrics['controlled_under_scoped_detected'])}."
        ),
        (
            "- Behavior-preserving or performance changes where raw AOS warned "
            f"even though adding a functional test was not the right action: "
            f"{_fraction(metrics['behavior_preserving_raw_warnings'])}."
        ),
        (
            "- Those noisy recommendations avoided by the calibrated scope: "
            f"{_fraction(metrics['noisy_recommendations_avoided_by_scope'])}."
        ),
        (
            "- Evidence integrity and semantic replay: "
            f"{_fraction(metrics['integrity'])}."
        ),
        "",
        "The useful calibration is therefore simple: run Change Proof when a pull "
        "request changes implementation and tests, or when an operator explicitly "
        "declares that the verifier should observe a behavior change. Skip ordinary "
        "functional Change Proof for behavior-preserving and performance-only work.",
        "",
        "## Cost",
        "",
        (
            f"AOS executed one HEAD run and two challenge runs. Median verifier work "
            f"was {metrics['median_verifier_work_ratio']}x one HEAD run "
            f"({metrics['median_verifier_total_seconds']} seconds in this small, fast "
            f"sample); median CLI wall time was "
            f"{metrics['median_cli_wall_seconds']} seconds."
        ),
        "",
        "This is acceptable for a targeted fast test command. It is not acceptable "
        "as an unconditional replay of a large test suite.",
        "",
        "## Where it fits",
        "",
        "| Existing tool | What it proves | What Change Proof adds |",
        "| --- | --- | --- |",
        (
            "| GitHub required checks | A registered result reached an accepted "
            "status for the commit | Whether the supplied verifier notices removal "
            "of the actual PR implementation |"
        ),
        (
            "| Codecov patch coverage | Changed lines executed | Whether test "
            "outcomes change; execution alone does not prove a meaningful "
            "assertion |"
        ),
        (
            "| Stryker or PIT | Tests kill many small synthetic mutants | One "
            "coarse, language-neutral counterfactual aligned with the submitted "
            "patch |"
        ),
        (
            "| SonarQube PR analysis | New static-analysis issues and quality-gate "
            "metrics | Dynamic sensitivity of the operator's own verifier |"
        ),
        "",
        "This is differentiated, not category-exclusive. Mutation testing is the "
        "closest established alternative and is stronger for fine-grained test "
        "quality. AOS may be easier to add across languages because it needs a Git "
        "diff and an existing command, but that advantage is not yet measured.",
        "",
        "## ROI gate",
        "",
        "Do not enable by default or define a paid offer until external use meets "
        "all of these conditions:",
        "",
        "1. At least 50 eligible pull requests across at least five independent "
        "repositories.",
        "2. At least 50% of warnings lead to an accepted test or verifier improvement.",
        "3. No more than 10% of warnings are judged irrelevant or wrong.",
        "4. No more than 10% of runs are inconclusive after one retry.",
        "5. Median added wall time stays below two minutes for the selected verifier.",
        "6. Setup takes at most ten minutes in at least 80% of repositories.",
        "7. At least 20% of accepted warnings change merge readiness or catch a "
        "weak test before review.",
        "8. At least half of trial repositories retain the plug-in after four weeks.",
        "",
        "The economic check is: expected avoided review and regression cost must "
        "exceed extra runner time plus warning-review time. The current study has no "
        "external accepted warning, decision change, retention, or willingness-to-pay "
        "observation, so ROI remains unproven.",
        "",
        "## Cases",
        "",
        "| Cohort | Pull request | Raw AOS | Calibrated action | Interpretation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in results["cases"]:
        lines.append(
            (
                "| {cohort} | [{repo}#{number}]({url}) | {verdict} | "
                "{action} | {value} |"
            ).format(
                cohort=str(case["cohort"]).replace("_", " "),
                repo=case["repository"],
                number=case["pr_number"],
                url=case["pr_url"],
                verdict=case["raw_verdict"],
                action=case["adaptive_action"],
                value=str(case["value_interpretation"]).replace("_", " "),
            )
        )
    lines.extend(
        [
            "",
            "## Limits",
            "",
            results["claim_boundary"],
            "",
            "The sample is exploratory, selected for reproducibility, Python-only, "
            "and contains one controlled counterfactual. It supports the next "
            "experiment, not a product-value or superiority claim.",
            "",
        ]
    )
    return "\n".join(lines)


def _json_text(value: dict[str, Any]) -> str:
    return json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n"


def main() -> int:
    args = _parser().parse_args()
    study_root = args.study_root.resolve()
    results = analyze(study_root)
    results_text = _json_text(results)
    report_text = render_report(results)
    results_path = study_root / "results.json"
    report_path = study_root / "REPORT.md"

    if args.check:
        stale = []
        if not results_path.is_file() or results_path.read_text(
            encoding="ascii"
        ) != results_text:
            stale.append(str(results_path))
        if not report_path.is_file() or report_path.read_text(
            encoding="utf-8"
        ) != report_text:
            stale.append(str(report_path))
        if stale:
            print("stale Change Proof benchmark: " + ", ".join(stale), file=sys.stderr)
            return 1
    else:
        results_path.write_text(results_text, encoding="ascii", newline="\n")
        report_path.write_text(report_text, encoding="utf-8", newline="\n")

    print(
        f"direction={results['product_direction']} "
        f"default={results['default_enablement']} "
        f"cases={results['metrics']['cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
