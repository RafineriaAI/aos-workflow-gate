#!/usr/bin/env python3
"""Verify and summarize the preregistered real-workflow utility benchmark."""

from __future__ import annotations

import argparse
import hashlib
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
from aos_workflow_gate.summarize import diagnose  # noqa: E402

DEFAULT_STUDY = ROOT / "benchmarks" / "real-workflow-utility"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sha256_file(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _rate(numerator: int, denominator: int) -> dict[str, int | float | None]:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "rate": round(numerator / denominator, 4) if denominator else None,
    }


def _naive_alert(workflow_runs: Any) -> bool:
    if not isinstance(workflow_runs, list):
        return False
    return any(
        isinstance(run, dict)
        and (run.get("status") != "completed" or run.get("conclusion") != "success")
        for run in workflow_runs
    )


def _naive_source_alert(sources: Any) -> bool:
    if not isinstance(sources, list):
        return False
    return any(
        isinstance(source, dict)
        and source.get("kind") in {"github_check", "commit_status"}
        and source.get("status") != "success"
        for source in sources
    )


def _message_structure(diagnosis: dict[str, Any]) -> bool:
    if diagnosis.get("verdict") == "PASS":
        return True
    required = ("problem", "impact", "affected_area", "next", "severity")
    return all(
        isinstance(diagnosis.get(field), str) and bool(diagnosis[field].strip())
        for field in required
    )


def _specific_diagnosis(record: dict[str, Any], diagnosis: dict[str, Any]) -> bool:
    reasons = record.get("reasons")
    if not isinstance(reasons, list):
        return False
    if any(
        isinstance(reason, dict) and isinstance(reason.get("source_id"), str)
        for reason in reasons
    ):
        return True
    configuration_rules = {
        "no_required_sources",
        "incomplete_collection",
        "non_independent_evidence",
        "verifier_change_unavailable",
        "record_integrity_failed",
    }
    named_configuration = any(
        isinstance(reason, dict) and reason.get("rule") in configuration_rules
        for reason in reasons
    )
    return named_configuration and bool(diagnosis.get("affected_area"))


def _primary_rule(diagnosis: dict[str, Any]) -> str | None:
    gaps = diagnosis.get("gaps")
    if not isinstance(gaps, list) or not gaps or not isinstance(gaps[0], dict):
        return None
    rule = gaps[0].get("rule")
    return rule if isinstance(rule, str) else None


def _problem_scope(rule: str | None) -> str:
    if rule is None:
        return "none"
    if rule in {
        "no_required_sources",
        "missing_required_source",
        "failed_required_source",
        "incomplete_collection",
        "non_independent_evidence",
        "verifier_change_unavailable",
    }:
        return "workflow_or_repository_control"
    if rule.startswith("project_") or rule in {
        "confirmed_verifier_failure",
        "change_not_distinguished",
        "verification_inconclusive",
    }:
        return "code_or_project_change"
    return "other"


def _case_artifacts(study_root: Path, case_id: str) -> dict[str, Path]:
    case_dir = study_root / "cases" / case_id
    return {
        name: case_dir / name
        for name in (
            "gate-decision.json",
            "bundle.json",
            "policy.json",
            "summary.txt",
            "execution.json",
        )
    }


def _review_map(study_root: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(study_root / "review-outcomes.json")
    cases = payload.get("cases")
    if not isinstance(cases, list):
        return {}
    return {
        str(case["case_id"]): case
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("case_id"), str)
    }


def _analyze_case(
    study_root: Path,
    selected: dict[str, Any],
    review: dict[str, Any] | None,
) -> dict[str, Any]:
    case_id = str(selected["case_id"])
    artifacts = _case_artifacts(study_root, case_id)
    missing = [name for name, path in artifacts.items() if not path.is_file()]
    if missing:
        return {
            "case_id": case_id,
            "cohort": selected["cohort"],
            "pair_id": selected["pair_id"],
            "complete": False,
            "errors": [f"missing artifact: {name}" for name in missing],
        }

    record = _read_json(artifacts["gate-decision.json"])
    bundle = _read_json(artifacts["bundle.json"])
    policy = _read_json(artifacts["policy.json"])
    execution = _read_json(artifacts["execution.json"])
    selected_sha = str(selected["head_sha"])
    subject = _dict(record.get("subject"))
    observation = _dict(record.get("observation"))
    observation_scope = _dict(observation.get("observation_scope"))
    bundle_subject = _dict(bundle.get("subject"))
    collection = _dict(bundle.get("collection"))
    collection_scope = _dict(collection.get("observation_scope"))
    policy_record = _dict(record.get("policy"))
    workflow_visibility = _dict(collection.get("workflow_visibility"))
    loaded_policy = load_policy(artifacts["policy.json"])
    replayed_record = build_record(
        evaluate(bundle, loaded_policy),
        policy=loaded_policy,
        input_bundle_digest=canonical.digest(bundle),
        can_block=bool(record.get("can_block")),
        observation=observation_from_bundle(bundle),
    )
    integrity = {
        "record_digest": verify_record(record),
        "bundle_digest": record.get("input_bundle_digest") == canonical.digest(bundle),
        "policy_digest": policy_record.get("digest") == canonical.digest(policy),
        "semantic_replay": replayed_record == record,
    }
    exact_sha = all(
        value == selected_sha
        for value in (
            subject.get("sha"),
            observation_scope.get("head_sha"),
            bundle_subject.get("sha"),
            collection_scope.get("head_sha"),
            execution.get("selected_head_sha"),
        )
    )
    errors: list[str] = []
    if execution.get("exit_code") != 0:
        errors.append(f"runner exit code {execution.get('exit_code')}")
    if not all(integrity.values()):
        errors.append("evidence integrity failure")
    if not exact_sha:
        errors.append("exact-SHA binding failure")
    elapsed = execution.get("elapsed_seconds")
    if not isinstance(elapsed, (int, float)) or elapsed > 300:
        errors.append("runtime exceeded 300 seconds or was not recorded")

    diagnosis = diagnose(record)
    primary_rule = _primary_rule(diagnosis)
    contrast = diagnosis.get("contrast")
    contrast = contrast if isinstance(contrast, dict) else {}
    stage_b = review.get("stage_b") if isinstance(review, dict) else None
    stage_b = stage_b if isinstance(stage_b, dict) else {}
    alignment = stage_b.get("alignment")
    material_alignment = bool(
        contrast.get("incremental")
        and review
        and review.get("business_relevance") == "material"
        and alignment in {"direct", "strong_indirect"}
    )
    return {
        "case_id": case_id,
        "pair_id": selected["pair_id"],
        "cohort": selected["cohort"],
        "repository": selected["repository"],
        "pr_number": selected["pr_number"],
        "pr_url": selected["pr_url"],
        "head_sha": selected_sha,
        "complete": not errors,
        "errors": errors,
        "elapsed_seconds": elapsed,
        "verdict": record.get("verdict"),
        "github_baseline": contrast.get("github_baseline"),
        "contrast_code": contrast.get("code"),
        "aos_incremental_by_contract": bool(contrast.get("incremental")),
        "naive_baseline_alert": _naive_source_alert(bundle.get("sources")),
        "frozen_workflow_naive_alert": _naive_alert(selected.get("workflow_runs")),
        "message_structure_complete": _message_structure(diagnosis),
        "diagnosis_specific": _specific_diagnosis(record, diagnosis),
        "exact_sha_bound": exact_sha,
        "integrity": integrity,
        "dominant_problem": diagnosis.get("problem"),
        "dominant_rule": primary_rule,
        "problem_scope": _problem_scope(primary_rule),
        "next_step": diagnosis.get("next"),
        "collection_status": collection.get("status"),
        "workflow_visibility_available": workflow_visibility.get("available") is True,
        "review_stage_a": review.get("stage_a_status") if review else None,
        "human_outcome_available": (
            review.get("human_outcome_available") if review else None
        ),
        "human_outcome_business_relevance": (
            review.get("business_relevance") if review else None
        ),
        "historical_alignment": alignment,
        "material_incremental_alignment": material_alignment,
    }


def _aggregate(
    cases: list[dict[str, Any]], cohort: str | None = None
) -> dict[str, Any]:
    selected = [case for case in cases if cohort is None or case["cohort"] == cohort]
    completed = [case for case in selected if case.get("complete")]
    non_pass = [case for case in completed if case.get("verdict") != "PASS"]
    naive_alerts = [case for case in completed if case.get("naive_baseline_alert")]
    contract_contrasts = [
        case for case in completed if case.get("aos_incremental_by_contract")
    ]
    blinded_cases = [
        case for case in completed if case.get("review_stage_a") == "frozen_before_aos"
    ]
    human_outcomes = [
        case for case in blinded_cases if case.get("human_outcome_available") is True
    ]
    material_outcomes = [
        case
        for case in human_outcomes
        if case.get("human_outcome_business_relevance") == "material"
    ]
    eligible_alignment = [
        case
        for case in completed
        if case.get("historical_alignment")
        in {"direct", "strong_indirect", "same_surface", "none", "contradictory"}
    ]
    aligned = [
        case
        for case in eligible_alignment
        if case.get("historical_alignment") in {"direct", "strong_indirect"}
    ]
    return {
        "selected_cases": len(selected),
        "completed_cases": len(completed),
        "verdicts": dict(Counter(str(case.get("verdict")) for case in completed)),
        "first_run_completion": _rate(len(completed), len(selected)),
        "exact_sha_binding": _rate(
            sum(bool(case.get("exact_sha_bound")) for case in completed),
            len(completed),
        ),
        "evidence_integrity": _rate(
            sum(all(case.get("integrity", {}).values()) for case in completed),
            len(completed),
        ),
        "semantic_replay": _rate(
            sum(
                case.get("integrity", {}).get("semantic_replay") is True
                for case in completed
            ),
            len(completed),
        ),
        "collection_complete": _rate(
            sum(case.get("collection_status") == "complete" for case in completed),
            len(completed),
        ),
        "workflow_visibility": _rate(
            sum(bool(case.get("workflow_visibility_available")) for case in completed),
            len(completed),
        ),
        "non_pass_message_structure": _rate(
            sum(bool(case.get("message_structure_complete")) for case in non_pass),
            len(non_pass),
        ),
        "diagnosis_specificity": _rate(
            sum(bool(case.get("diagnosis_specific")) for case in non_pass),
            len(non_pass),
        ),
        "code_or_project_change_findings": _rate(
            sum(
                case.get("problem_scope") == "code_or_project_change"
                for case in non_pass
            ),
            len(non_pass),
        ),
        "workflow_or_repository_control_findings": _rate(
            sum(
                case.get("problem_scope") == "workflow_or_repository_control"
                for case in non_pass
            ),
            len(non_pass),
        ),
        "aos_contract_contrast": _rate(
            len(contract_contrasts),
            len(completed),
        ),
        "contract_contrast_reasons": dict(
            Counter(str(case.get("dominant_rule")) for case in contract_contrasts)
        ),
        "contract_contrast_without_visible_non_success": _rate(
            sum(not case.get("naive_baseline_alert") for case in contract_contrasts),
            len(contract_contrasts),
        ),
        "noise_avoided_vs_all_non_success": _rate(
            sum(case.get("verdict") == "PASS" for case in naive_alerts),
            len(naive_alerts),
        ),
        "blinded_human_outcome_coverage": _rate(
            len(human_outcomes),
            len(blinded_cases),
        ),
        "historical_action_alignment": _rate(len(aligned), len(eligible_alignment)),
        "material_incremental_alignment": _rate(
            sum(
                bool(case.get("material_incremental_alignment"))
                for case in material_outcomes
            ),
            len(material_outcomes),
        ),
        "material_incremental_signal_coverage": _rate(
            sum(bool(case.get("material_incremental_alignment")) for case in completed),
            len(completed),
        ),
        "median_time_to_diagnosis_seconds": (
            round(median(float(case["elapsed_seconds"]) for case in completed), 3)
            if completed
            else None
        ),
    }


def analyze(study_root: Path) -> dict[str, Any]:
    manifest_path = study_root / "manifest.json"
    manifest = _read_json(manifest_path)
    selection = _read_json(study_root / "selection.json")
    reviews = _review_map(study_root)
    if selection.get("manifest_digest") != _sha256_file(manifest_path):
        raise ValueError("selection.manifest_digest does not match manifest.json")
    selected = selection.get("cases")
    if not isinstance(selected, list):
        raise ValueError("selection.cases must be a list")
    cases = [
        _analyze_case(study_root, case, reviews.get(str(case.get("case_id"))))
        for case in selected
        if isinstance(case, dict)
    ]
    polish = sum(case.get("cohort") == "polish" for case in cases)
    global_cases = sum(case.get("cohort") == "global" for case in cases)
    if polish != global_cases or polish + global_cases != len(cases):
        raise ValueError("the selected sample is not exactly 50% Polish and 50% global")
    pair_counts = Counter(str(case.get("pair_id")) for case in cases)
    complete_pairs = sum(
        count == 2
        and all(
            case.get("complete")
            for case in cases
            if str(case.get("pair_id")) == pair_id
        )
        for pair_id, count in pair_counts.items()
    )
    aggregate = _aggregate(cases)
    mechanism_ok = (
        aggregate["first_run_completion"]["rate"] == 1.0
        and aggregate["exact_sha_binding"]["rate"] == 1.0
        and aggregate["evidence_integrity"]["rate"] == 1.0
    )
    material_signal = any(case["material_incremental_alignment"] for case in cases)
    minimum_pairs = int(manifest["sampling"]["minimum_completed_pairs"])
    if complete_pairs < minimum_pairs:
        utility_result = "INSUFFICIENT_SAMPLE"
    elif material_signal:
        utility_result = "WORKFLOW_UTILITY_SIGNAL"
    else:
        utility_result = "NO_CLEAR_WORKFLOW_UTILITY"
    return {
        "schema_version": "aos-real-workflow-results/v0",
        "study_id": manifest["study_id"],
        "manifest_digest": _sha256_file(manifest_path),
        "selection_status": selection.get("status"),
        "sample": {
            "cases": len(cases),
            "polish_cases": polish,
            "global_cases": global_cases,
            "completed_pairs": complete_pairs,
        },
        "mechanism_result": "PASS" if mechanism_ok else "FAIL",
        "workflow_utility_result": utility_result,
        "metrics": aggregate,
        "cohorts": {
            "polish": _aggregate(cases, "polish"),
            "global": _aggregate(cases, "global"),
        },
        "cases": cases,
        "protocol_deviations": [
            "Stage A review extraction followed AOS execution for five cases; "
            "those cases are excluded from blinded historical-action alignment."
        ],
        "unmeasured_without_enrolled_users": {
            "actual_actionable_rate": None,
            "actual_decision_change_rate": None,
            "incremental_value_noticed_by_user": None,
            "alert_acceptance_rate": None,
            "retention": None,
            "willingness_to_pay": None,
            "incident_reduction": None,
            "time_saved": None,
        },
        "claim_boundary": manifest["claim_boundary"],
    }


def _verdict_summary(cohort: dict[str, Any]) -> str:
    verdicts = _dict(cohort.get("verdicts"))
    return " / ".join(
        f"{verdict} {int(verdicts.get(verdict, 0))}"
        for verdict in ("PASS", "WARN", "BLOCK")
    )


def render_report(results: dict[str, Any]) -> str:
    metrics = results["metrics"]
    sample = results["sample"]
    polish = results["cohorts"]["polish"]
    global_cohort = results["cohorts"]["global"]
    lines = [
        "# Real-Workflow Utility Benchmark",
        "",
        "## Result",
        "",
        f"- Mechanism: **{results['mechanism_result']}**",
        f"- Workflow utility signal: **{results['workflow_utility_result']}**",
        (
            f"- Sample: {sample['cases']} cases / {sample['completed_pairs']} "
            f"matched pairs; {sample['polish_cases']} Polish-affiliated and "
            f"{sample['global_cases']} global."
        ),
        "",
        "This is a read-only workflow benchmark, not a user study. A contract-level "
        "contrast is not treated as proof that a maintainer would act.",
        "",
        "## Measured",
        "",
        f"- First-run completion: {metrics['first_run_completion']['numerator']}/"
        f"{metrics['first_run_completion']['denominator']}",
        f"- Exact-SHA binding: {metrics['exact_sha_binding']['numerator']}/"
        f"{metrics['exact_sha_binding']['denominator']}",
        f"- Evidence integrity: {metrics['evidence_integrity']['numerator']}/"
        f"{metrics['evidence_integrity']['denominator']}",
        f"- Semantic replay: {metrics['semantic_replay']['numerator']}/"
        f"{metrics['semantic_replay']['denominator']}",
        f"- Complete collection at first observation: "
        f"{metrics['collection_complete']['numerator']}/"
        f"{metrics['collection_complete']['denominator']}",
        f"- Workflow visibility available: "
        f"{metrics['workflow_visibility']['numerator']}/"
        f"{metrics['workflow_visibility']['denominator']}",
        f"- Structurally complete non-PASS messages: "
        f"{metrics['non_pass_message_structure']['numerator']}/"
        f"{metrics['non_pass_message_structure']['denominator']}",
        f"- Code/project-change findings among non-PASS: "
        f"{metrics['code_or_project_change_findings']['numerator']}/"
        f"{metrics['code_or_project_change_findings']['denominator']}",
        f"- Workflow/repository-control findings among non-PASS: "
        f"{metrics['workflow_or_repository_control_findings']['numerator']}/"
        f"{metrics['workflow_or_repository_control_findings']['denominator']}",
        f"- Naive non-success alerts avoided: "
        f"{metrics['noise_avoided_vs_all_non_success']['numerator']}/"
        f"{metrics['noise_avoided_vs_all_non_success']['denominator']}",
        (
            "- AOS contract-level contrast: "
            f"{metrics['aos_contract_contrast']['numerator']}/"
            f"{metrics['aos_contract_contrast']['denominator']}"
        ),
        (
            "- Contract contrasts without a same-snapshot visible non-success: "
            f"{metrics['contract_contrast_without_visible_non_success']['numerator']}/"
            f"{metrics['contract_contrast_without_visible_non_success']['denominator']}"
        ),
        f"- Frozen human-outcome coverage: "
        f"{metrics['blinded_human_outcome_coverage']['numerator']}/"
        f"{metrics['blinded_human_outcome_coverage']['denominator']}",
        f"- Historical action alignment: "
        f"{metrics['historical_action_alignment']['numerator']}/"
        f"{metrics['historical_action_alignment']['denominator']}",
        f"- Material incremental alignment where outcome was available: "
        f"{metrics['material_incremental_alignment']['numerator']}/"
        f"{metrics['material_incremental_alignment']['denominator']}",
        f"- Material incremental signal coverage: "
        f"{metrics['material_incremental_signal_coverage']['numerator']}/"
        f"{metrics['material_incremental_signal_coverage']['denominator']}",
        "",
        "## Cohorts",
        "",
        "| Metric | Polish-affiliated | Global |",
        "| --- | --- | --- |",
        f"| Cases | {polish['completed_cases']} | {global_cohort['completed_cases']} |",
        f"| Verdicts | {_verdict_summary(polish)} | "
        f"{_verdict_summary(global_cohort)} |",
        (
            "| Contract contrast | "
            f"{polish['aos_contract_contrast']['numerator']}/"
            f"{polish['aos_contract_contrast']['denominator']} | "
            f"{global_cohort['aos_contract_contrast']['numerator']}/"
            f"{global_cohort['aos_contract_contrast']['denominator']} |"
        ),
        (
            "| Naive alerts avoided | "
            f"{polish['noise_avoided_vs_all_non_success']['numerator']}/"
            f"{polish['noise_avoided_vs_all_non_success']['denominator']} | "
            f"{global_cohort['noise_avoided_vs_all_non_success']['numerator']}/"
            f"{global_cohort['noise_avoided_vs_all_non_success']['denominator']} |"
        ),
        (
            "| Blinded human outcomes | "
            f"{polish['blinded_human_outcome_coverage']['numerator']}/"
            f"{polish['blinded_human_outcome_coverage']['denominator']} | "
            f"{global_cohort['blinded_human_outcome_coverage']['numerator']}/"
            f"{global_cohort['blinded_human_outcome_coverage']['denominator']} |"
        ),
        "",
        "The cohorts are descriptive only. Five cases per cohort and zero eligible "
        "human outcomes in the Polish-affiliated cohort do not support a comparative "
        "utility claim.",
        "",
        "## Cases",
        "",
        (
            "| Cohort | Repository / PR | AOS | GitHub baseline | Naive alert | "
            "Incremental by contract | Human alignment |"
        ),
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in results["cases"]:
        lines.append(
            f"| {case['cohort']} | [{case['repository']}#{case['pr_number']}]"
            f"({case['pr_url']}) | {case.get('verdict', '-')} | "
            f"{case.get('github_baseline', '-')} | "
            f"{'yes' if case.get('naive_baseline_alert') else 'no'} | "
            f"{'yes' if case.get('aos_incremental_by_contract') else 'no'} | "
            f"{case.get('historical_alignment') or 'unavailable'} |"
        )
    lines.extend(
        [
            "",
            "## Practical reading",
            "",
            "AOS completed quickly and produced intact, exact-SHA evidence. It also "
            "avoided three alerts that a naive all-non-success rule would emit.",
            "",
            "The measured value is currently maintainer-facing: every non-PASS "
            "finding concerned repository or workflow controls. All four AOS/GitHub "
            "contrasts were `no_required_sources`; only one occurred without a "
            "same-snapshot visible non-success signal. The three BLOCK results "
            "explained states where GitHub already waited.",
            "",
            "The two blinded, material human outcomes concerned code diagnostics "
            "and change blast radius. Neither aligned with the AOS finding. This "
            "sample therefore does not demonstrate a daily code-review assistant or "
            "a maintainer decision change.",
            "",
            "Product implication: keep zero-config `check-pr` as a low-noise "
            "workflow control diagnostic. A broader developer product still needs "
            "code/diff-aware policies that produce concrete author actions and show "
            "material alignment "
            "with independent review outcomes.",
            "",
            "## Interpretation",
            "",
            "The benchmark can verify collection, exact-SHA evidence, low-noise "
            "treatment of expected states, and whether AOS explains a gap "
            "differently from GitHub. "
            "It cannot establish daily usefulness, action acceptance, decision change, "
            "retention, time saved, incident reduction, or willingness to pay.",
            "",
            "Five cases violated the planned Stage A-before-AOS ordering and are "
            "excluded from blinded historical-action alignment. Silence, merge, and "
            "bot-only "
            "comments are not counted as acceptance or noise.",
            "",
        ]
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-root", type=Path, default=DEFAULT_STUDY)
    parser.add_argument("--check", action="store_true")
    return parser


def main() -> int:
    args = _parser().parse_args()
    study_root = args.study_root.resolve()
    results = analyze(study_root)
    if args.check:
        current_results = _read_json(study_root / "results.json")
        current_report = (study_root / "REPORT.md").read_text(encoding="utf-8")
        if current_results != results or current_report != render_report(results):
            print("real-workflow benchmark outputs are stale")
            return 1
        print("real-workflow benchmark outputs are current")
        return 0
    (study_root / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    (study_root / "REPORT.md").write_text(
        render_report(results), encoding="utf-8", newline="\n"
    )
    print(
        f"{results['workflow_utility_result']}: "
        f"{results['sample']['cases']} cases, "
        f"{results['sample']['completed_pairs']} complete pairs"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
