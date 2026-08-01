#!/usr/bin/env python3
"""Evaluate the calibrated holdout and answer whether AOS should continue."""

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

from aos_workflow_gate.summarize import diagnose  # noqa: E402
from tools.real_workflow_utility import (  # noqa: E402
    _analyze_case,
    _dict,
    _rate,
    _read_json,
    _sha256_file,
)

DEFAULT_STUDY = ROOT / "benchmarks" / "adaptive-value-calibration"
VALUE_CLASSES = {
    "new_action",
    "useful_explanation",
    "duplicate",
    "unrelated",
    "no_problem_observed",
    "insufficient",
}
ALIGNED = {"direct", "strong_indirect"}


def _sha256_portable_text_file(path: Path) -> str:
    """Hash repository text without platform-specific line endings."""
    content = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-root", type=Path, default=DEFAULT_STUDY)
    parser.add_argument("--check", action="store_true")
    return parser


def _review_map(path: Path) -> dict[str, dict[str, Any]]:
    payload = _read_json(path)
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise ValueError(f"{path}: cases must be a list")
    return {
        str(case["case_id"]): case
        for case in cases
        if isinstance(case, dict) and isinstance(case.get("case_id"), str)
    }


def _assert_frozen_stage_a(study_root: Path) -> None:
    frozen = _read_json(study_root / "review-outcomes-stage-a.json")
    completed = _read_json(study_root / "review-outcomes.json")
    completed.pop("stage_b_completed_at", None)
    completed["status"] = "STAGE_A_FROZEN_BEFORE_AOS"
    cases = completed.get("cases")
    if isinstance(cases, list):
        for case in cases:
            if isinstance(case, dict):
                case.pop("stage_b", None)
    if completed != frozen:
        raise ValueError("Stage A changed after AOS was revealed")


def _plain_message(
    study_root: Path,
    case_id: str,
    calibration: dict[str, Any],
) -> dict[str, Any]:
    record = _read_json(study_root / "cases" / case_id / "gate-decision.json")
    diagnosis = diagnose(record)
    if diagnosis.get("verdict") == "PASS":
        return {
            "complete": True,
            "plain": True,
            "internal_terms": [],
            "fields": {},
        }
    required = calibration["plain_language"]["required_fields"]
    fields = {field: diagnosis.get(field) for field in required}
    complete = all(
        isinstance(value, str) and bool(value.strip()) for value in fields.values()
    )
    main_text = " ".join(str(value) for value in fields.values()).lower()
    internal_terms = [
        term
        for term in calibration["plain_language"][
            "internal_terms_not_allowed_in_main_message"
        ]
        if str(term).lower() in main_text
    ]
    return {
        "complete": complete,
        "plain": complete and not internal_terms,
        "internal_terms": internal_terms,
        "fields": fields,
    }


def _analyze_holdout_case(
    study_root: Path,
    selected: dict[str, Any],
    review: dict[str, Any],
    calibration: dict[str, Any],
) -> dict[str, Any]:
    case = _analyze_case(study_root, selected, review)
    case_id = str(selected["case_id"])
    message = _plain_message(study_root, case_id, calibration)
    stage_b = _dict(review.get("stage_b"))
    value_class = stage_b.get("value_class")
    if value_class not in VALUE_CLASSES:
        raise ValueError(f"{case_id}: invalid or missing Stage B value_class")
    alignment = stage_b.get("alignment")
    material = review.get("business_relevance") == "material"
    aligned = alignment in ALIGNED
    case.update(
        {
            "human_outcome": review.get("outcome"),
            "requested_action": review.get("requested_action"),
            "action_taken": review.get("action_taken"),
            "business_risk": review.get("business_risk"),
            "business_relevance": review.get("business_relevance"),
            "historical_alignment": alignment,
            "value_class": value_class,
            "value_rationale": stage_b.get("rationale"),
            "plain_message_complete": message["complete"],
            "plain_main_message": message["plain"],
            "main_message_internal_terms": message["internal_terms"],
            "new_action": value_class == "new_action",
            "useful_explanation": value_class == "useful_explanation",
            "material_review_problem": material,
            "material_review_aligned": material and aligned,
            "material_review_missed": material and not aligned,
        }
    )
    return case


def _community_checks(root: Path) -> dict[str, bool]:
    readme = (root / "README.md").read_text(encoding="utf-8")
    contributing = (root / "CONTRIBUTING.md").read_text(encoding="utf-8")
    maturity = (root / "docs" / "MATURITY.md").read_text(encoding="utf-8")
    license_text = (root / "LICENSE").read_text(encoding="utf-8")
    return {
        "free_open_source_license": "Apache License" in license_text,
        "repeatable_local_setup": "python -m pip install -e" in contributing,
        "test_commands_documented": "python -m pytest" in contributing,
        "contribution_workflow_documented": "## Change workflow" in contributing,
        "preview_maturity_is_explicit": "Preview" in maturity,
        "readme_says_who_needs_it": "AOS is useful when" in readme,
        "readme_says_who_does_not": "AOS is probably not useful when" in readme,
        "readme_bounds_product_role": (
            "AOS is not another AI reviewer" in readme
            and "does not infer business" in readme
            and "intent or prove that the code is correct" in readme
        ),
        "readme_states_value_is_unproven": (
            "Everyday usefulness has not been independently proven" in readme
        ),
    }


def _aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    completed = [case for case in cases if case.get("complete")]
    non_pass = [case for case in completed if case.get("verdict") != "PASS"]
    material = [case for case in completed if case.get("material_review_problem")]
    classes = Counter(str(case.get("value_class")) for case in completed)
    return {
        "selected_cases": len(cases),
        "completed_cases": len(completed),
        "verdicts": dict(Counter(str(case.get("verdict")) for case in completed)),
        "mechanism_integrity": _rate(
            sum(
                case.get("exact_sha_bound") is True
                and all(_dict(case.get("integrity")).values())
                for case in completed
            ),
            len(completed),
        ),
        "exact_sha_binding": _rate(
            sum(case.get("exact_sha_bound") is True for case in completed),
            len(completed),
        ),
        "semantic_replay": _rate(
            sum(
                _dict(case.get("integrity")).get("semantic_replay") is True
                for case in completed
            ),
            len(completed),
        ),
        "human_outcome_coverage": _rate(
            sum(case.get("human_outcome_available") is True for case in completed),
            len(completed),
        ),
        "plain_main_message": _rate(
            sum(case.get("plain_main_message") is True for case in non_pass),
            len(non_pass),
        ),
        "new_action": _rate(classes["new_action"], len(completed)),
        "useful_explanation": _rate(classes["useful_explanation"], len(completed)),
        "duplicate": _rate(classes["duplicate"], len(completed)),
        "unrelated": _rate(classes["unrelated"], len(completed)),
        "material_alignment": _rate(
            sum(case.get("material_review_aligned") is True for case in material),
            len(material),
        ),
        "material_miss": _rate(
            sum(case.get("material_review_missed") is True for case in material),
            len(material),
        ),
        "median_time_to_diagnosis_seconds": (
            round(median(float(case["elapsed_seconds"]) for case in completed), 3)
            if completed
            else None
        ),
    }


def _decision(
    metrics: dict[str, Any],
    calibration: dict[str, Any],
    community_checks: dict[str, bool],
) -> tuple[str, str]:
    rules = calibration["decision_rules"]
    enough_cases = (
        metrics["completed_cases"] >= rules["minimum_completed_holdout_cases"]
    )
    outcome_rate = metrics["human_outcome_coverage"]["rate"]
    enough_outcomes = (
        isinstance(outcome_rate, float)
        and outcome_rate >= rules["minimum_human_outcome_coverage"]
    )
    if not enough_cases or not enough_outcomes:
        return "INSUFFICIENT_SAMPLE", "INSUFFICIENT_SAMPLE"

    mechanism_rate = metrics["mechanism_integrity"]["rate"]
    if mechanism_rate != 1.0:
        return "STOP_PENDING_NEW_EVIDENCE", "HOLD_BEFORE_COMMUNITY_RELEASE"

    current = rules["continue_current_product_direction"]
    new_actions = metrics["new_action"]["numerator"]
    alignment_rate = metrics["material_alignment"]["rate"] or 0.0
    miss_rate = metrics["material_miss"]["rate"] or 0.0
    if (
        new_actions >= current["minimum_new_action_cases"]
        and alignment_rate >= current["minimum_material_alignment_rate"]
        and miss_rate <= current["maximum_material_miss_rate"]
    ):
        development = "CONTINUE_CURRENT_DIRECTION"
    elif (
        metrics["new_action"]["numerator"] == 0
        and metrics["useful_explanation"]["numerator"] == 0
    ):
        development = "STOP_PENDING_NEW_EVIDENCE"
    else:
        development = "NARROW_OR_PIVOT"

    community_rule = rules["open_community_preview"]
    plain_rate = metrics["plain_main_message"]["rate"] or 0.0
    community_ready = (
        mechanism_rate == community_rule["mechanism_integrity_rate"]
        and plain_rate >= community_rule["minimum_plain_main_message_rate"]
        and all(community_checks.values())
    )
    community = (
        "OPEN_AS_EXPERIMENTAL_PREVIEW"
        if community_ready
        else "HOLD_BEFORE_COMMUNITY_RELEASE"
    )
    return development, community


def analyze(study_root: Path) -> dict[str, Any]:
    manifest_path = study_root / "manifest.json"
    calibration_path = study_root / "calibration.json"
    selection_path = study_root / "selection.json"
    stage_a_path = study_root / "review-outcomes-stage-a.json"
    manifest = _read_json(manifest_path)
    calibration = _read_json(calibration_path)
    selection = _read_json(selection_path)
    reviews = _review_map(study_root / "review-outcomes.json")

    expected_digests = {
        "manifest_digest": _sha256_portable_text_file(manifest_path),
        "calibration_digest": _sha256_portable_text_file(calibration_path),
        "stage_a_digest": _sha256_portable_text_file(stage_a_path),
    }
    for field, expected in expected_digests.items():
        if selection.get(field) != expected:
            raise ValueError(f"selection.{field} does not match its frozen file")
    _assert_frozen_stage_a(study_root)

    discovery = calibration["discovery_source"]
    for path_field, digest_field in (
        ("results_path", "results_digest"),
        ("report_path", "report_digest"),
    ):
        path = ROOT / discovery[path_field]
        if _sha256_file(path) != discovery[digest_field]:
            raise ValueError(f"calibration discovery artifact changed: {path}")

    raw_cases = selection.get("cases")
    if not isinstance(raw_cases, list):
        raise ValueError("selection.cases must be a list")
    cases = [
        _analyze_holdout_case(
            study_root,
            selected,
            reviews[str(selected["case_id"])],
            calibration,
        )
        for selected in raw_cases
        if isinstance(selected, dict)
    ]
    polish = sum(case.get("cohort") == "polish" for case in cases)
    global_cases = sum(case.get("cohort") == "global" for case in cases)
    if polish != 5 or global_cases != 5:
        raise ValueError(
            "holdout must contain exactly five Polish and five global cases"
        )

    discovery_results = _read_json(ROOT / discovery["results_path"])
    discovery_repositories = {
        str(case.get("repository"))
        for case in discovery_results.get("cases", [])
        if isinstance(case, dict)
    }
    overlap = sorted(
        {str(case.get("repository")) for case in cases} & discovery_repositories
    )
    if overlap:
        raise ValueError(f"holdout repository leaked from discovery: {overlap}")

    metrics = _aggregate(cases)
    community_checks = _community_checks(ROOT)
    development, community = _decision(metrics, calibration, community_checks)
    return {
        "schema_version": "aos-adaptive-value-results/v0",
        "study_id": manifest["study_id"],
        "manifest_digest": _sha256_portable_text_file(manifest_path),
        "calibration_digest": _sha256_portable_text_file(calibration_path),
        "stage_a_digest": _sha256_portable_text_file(stage_a_path),
        "sample": {
            "cases": len(cases),
            "polish_cases": polish,
            "global_cases": global_cases,
        },
        "mechanism_result": (
            "PASS" if metrics["mechanism_integrity"]["rate"] == 1.0 else "FAIL"
        ),
        "development_decision": development,
        "community_decision": community,
        "metrics": metrics,
        "community_checks": community_checks,
        "cohorts": {
            cohort: _aggregate([case for case in cases if case["cohort"] == cohort])
            for cohort in ("polish", "global")
        },
        "cases": cases,
        "claim_boundary": manifest["claim_boundary"],
        "unmeasured_without_users": manifest["unmeasured_without_users"],
    }


def _rate_text(metric: dict[str, Any]) -> str:
    return f"{metric['numerator']}/{metric['denominator']}"


def render_report(results: dict[str, Any]) -> str:
    metrics = results["metrics"]
    lines = [
        "# Should AOS continue?",
        "",
        "## Decision",
        "",
        f"- Product direction: **{results['development_decision']}**",
        f"- Community release: **{results['community_decision']}**",
        f"- Mechanism: **{results['mechanism_result']}**",
        "- Holdout: 10 real pull requests; 5 Polish-affiliated and 5 global.",
        "",
        "## In plain language",
        "",
        (
            "AOS ran reliably and explained one required GitHub check that did not "
            "run. It did not identify any of the material code, data, runtime or "
            "review problems independently found by people in this holdout."
        ),
        "",
        (
            "That means the current GitHub gate may help maintainers understand "
            "repository controls, but this benchmark does not support positioning "
            "it as a general daily code-review assistant."
        ),
        "",
        "The repository can be shared as a free experiment if it says this clearly. "
        "Community use should be treated as problem discovery, not proof that the "
        "product is already needed.",
        "",
        "## Wniosek po polsku",
        "",
        (
            "Mechanizm działa poprawnie, ale w tej próbie AOS nie wskazał żadnej "
            "nowej czynności odpowiadającej istotnym problemom znalezionym przez "
            "ludzi. Warto zachować wąską kontrolę workflow i udostępnić projekt "
            "bezpłatnie jako eksperyment. Nie ma jeszcze podstaw, by przedstawiać "
            "go jako ogólnego pomocnika do recenzji kodu."
        ),
        "",
        "## What was measured",
        "",
        (
            "- Exact commit and replay integrity: "
            f"{_rate_text(metrics['mechanism_integrity'])}"
        ),
        (
            "- Human review outcome available: "
            f"{_rate_text(metrics['human_outcome_coverage'])}"
        ),
        (
            "- Non-PASS messages understandable without internal terms: "
            f"{_rate_text(metrics['plain_main_message'])}"
        ),
        (
            "- New useful action not already visible in GitHub: "
            f"{_rate_text(metrics['new_action'])}"
        ),
        (
            "- Useful explanation of an existing GitHub state: "
            f"{_rate_text(metrics['useful_explanation'])}"
        ),
        (
            "- Material human-review problems matched by AOS: "
            f"{_rate_text(metrics['material_alignment'])}"
        ),
        (
            "- Material human-review problems missed by AOS: "
            f"{_rate_text(metrics['material_miss'])}"
        ),
        (
            "- Median time to result: "
            f"{metrics['median_time_to_diagnosis_seconds']} seconds"
        ),
        "",
        "## Who may need it",
        "",
        (
            "- Maintainers who rely on GitHub required checks and need to know why "
            "one did not run."
        ),
        (
            "- Teams that want a replayable record of the checks used for one "
            "exact commit."
        ),
        (
            "- Open-source contributors willing to test whether other repository "
            "rules should be modeled."
        ),
        "",
        "## Who probably does not need it yet",
        "",
        "- A developer looking for code review, bug finding or architecture advice.",
        "- A small repository with no required GitHub checks.",
        "- A team expecting proof that PASS means the code is safe.",
        "",
        "## Holdout cases",
        "",
        "| Cohort | Pull request | AOS | Human issue | Value class |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in results["cases"]:
        lines.append(
            (
                "| {cohort} | [{repo}#{number}]({url}) | {verdict} | {risk} | {value} |"
            ).format(
                cohort=case["cohort"],
                repo=case["repository"],
                number=case["pr_number"],
                url=case["pr_url"],
                verdict=case["verdict"],
                risk=str(case.get("business_risk", "unknown")).replace("_", " "),
                value=case["value_class"].replace("_", " "),
            )
        )
    lines.extend(
        [
            "",
            "## Recommended next move",
            "",
            "Keep the exact-commit workflow gate narrow. Before adding more platform "
            "features, test one diff-aware rule that can name a file, explain a real "
            "risk and propose an action that matches independent human review.",
            "",
            "Open development to the community only as a free experimental preview. "
            "Ask contributors for falsifiable cases: a missed required control, a "
            "wrong warning, or a concrete review action AOS should have suggested.",
            "",
            "## Limits",
            "",
            results["claim_boundary"],
            "",
            "This historical holdout cannot measure actual adoption, retained use, "
            "accepted recommendations, live decision changes, time saved or "
            "willingness to pay.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
        newline="\n",
    )


def main() -> int:
    args = _parser().parse_args()
    study_root = args.study_root.resolve()
    results = analyze(study_root)
    report = render_report(results)
    results_path = study_root / "results.json"
    report_path = study_root / "REPORT.md"
    expected_json = (
        json.dumps(results, ensure_ascii=True, indent=2, sort_keys=True) + "\n"
    )
    expected_report = report

    if args.check:
        stale = []
        if (
            not results_path.is_file()
            or results_path.read_text(encoding="ascii") != expected_json
        ):
            stale.append(str(results_path))
        if (
            not report_path.is_file()
            or report_path.read_text(encoding="utf-8") != expected_report
        ):
            stale.append(str(report_path))
        if stale:
            print(
                "stale adaptive value benchmark: " + ", ".join(stale), file=sys.stderr
            )
            return 1
    else:
        _write_json(results_path, results)
        report_path.write_text(report, encoding="utf-8", newline="\n")

    print(
        f"development={results['development_decision']} "
        f"community={results['community_decision']} "
        f"cases={results['sample']['cases']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
