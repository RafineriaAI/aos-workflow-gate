"""The committed governance benchmark cases must replay forever.

Every case in benchmarks/cases/ is verified offline by the harness on
every CI run, and the verdict spine of the benchmark (real PASS, real
WARN, real-signal counterfactual BLOCK) is asserted against the
committed records — a silent regression in either would invalidate the
public claim.
"""

from __future__ import annotations

import json
from pathlib import Path

from aos_workflow_gate.bench import verify_case

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "benchmarks" / "cases"

EXPECTED = {
    "agent-pr36-preflight": "PASS",
    "green-but-incomplete-pr22": "WARN",
    "v0110-incident-counterfactual": "BLOCK",
}


def test_all_committed_cases_verify_offline() -> None:
    found = {path.name for path in CASES.iterdir() if path.is_dir()}
    assert found == set(EXPECTED), "benchmark cases drifted from the suite"
    for case_id in sorted(EXPECTED):
        report = verify_case(CASES / case_id)
        assert report["ok"] is True, (case_id, report["failed"])
        assert "offline_replay" in report["verified"], case_id
        assert "patch_authorship" in report["unverifiable"], case_id


def test_verdict_spine_matches_the_public_claim() -> None:
    for case_id, verdict in EXPECTED.items():
        record = json.loads(
            (CASES / case_id / "gate-decision.json").read_text(
                encoding="utf-8"
            )
        )
        assert record["verdict"] == verdict, case_id


def test_incident_case_names_the_failed_control() -> None:
    record = json.loads(
        (CASES / "v0110-incident-counterfactual" / "gate-decision.json")
        .read_text(encoding="utf-8")
    )
    reasons = {
        (reason["rule"], reason["source_id"])
        for reason in record["reasons"]
    }
    assert (
        "failed_required_source", "AOS Workflow Gate Self / advisory"
    ) in reasons
    # the baseline said merge-ready: the required CI check was green
    bundle = json.loads(
        (CASES / "v0110-incident-counterfactual" / "bundle.json")
        .read_text(encoding="utf-8")
    )
    by_id = {source["id"]: source for source in bundle["sources"]}
    assert by_id["AOS Workflow Gate CI / validate"]["status"] == "success"


def test_gap_case_names_the_skipped_control() -> None:
    record = json.loads(
        (CASES / "green-but-incomplete-pr22" / "gate-decision.json")
        .read_text(encoding="utf-8")
    )
    assert any(
        reason["rule"] == "advisory_warning"
        and "no-checkout" in str(reason["source_id"])
        for reason in record["reasons"]
    )


def test_cases_declare_dogfooding_provenance() -> None:
    for case_id in EXPECTED:
        case = json.loads(
            (CASES / case_id / "case.json").read_text(encoding="utf-8")
        )
        assert case["classification"] in (
            "real_pass_control",
            "real_gap_warn",
            "controlled_counterfactual_block",
        )
        assert case["baseline"]["github_merge_ready"] is True
        assert "Claude Code" in case["attestation"]["statement"]
        action = json.loads(
            (CASES / case_id / "action.json").read_text(encoding="utf-8")
        )
        assert action["agent"]["operated_by"] == "maintainer"
