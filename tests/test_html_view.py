from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical
from aos_workflow_gate.cli import main
from aos_workflow_gate.summarize import diagnose, render_html

ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests" / "golden"

CASES = (
    "gate-decision",
    "aos-kernel-gate-decision",
    "green-but-incomplete-record",
    "pr-evidence-record",
    "check-pr-record",
    "zero-required-record",
)


def _record(name: str = "gate-decision") -> dict[str, Any]:
    return json.loads(
        (ROOT / "examples" / f"{name}.json").read_text(encoding="utf-8")
    )


@pytest.mark.parametrize("name", CASES)
def test_html_matches_golden(name: str) -> None:
    text, intact = render_html(_record(name))
    assert intact
    golden_path = GOLDEN / f"{name}.html"
    if os.environ.get("AOS_UPDATE_GOLDEN") == "1":
        golden_path.write_text(text, encoding="utf-8", newline="\n")
    assert text == golden_path.read_text(encoding="utf-8")


def test_html_is_deterministic_and_self_contained() -> None:
    record = _record()
    first, _ = render_html(record)
    second, _ = render_html(record)
    assert first == second
    lowered = first.lower()
    for banned in ("<script", "http://", "https://", "src=", "@import"):
        assert banned not in lowered, banned
    assert "UNSIGNED_NOT_OFFICIAL" in first
    assert "background:#fff" in first


def test_html_says_the_same_as_markdown() -> None:
    record = _record()
    diag = diagnose(record)
    text, _ = render_html(record)
    assert str(diag["verdict"]) in text
    decoded = text.replace("&quot;", '"').replace(
        "&#x27;", "'"
    ).replace("&amp;", "&")
    for key in ("problem", "impact", "affected_area", "severity", "next"):
        assert diag[key] in decoded
    assert str(diag["record_digest"]) in text


@pytest.mark.parametrize(
    ("verdict", "expected"),
    [
        (
            "PASS",
            "All controls required by this policy passed. Normal code and "
            "product review still apply.",
        ),
        ("WARN", "Approval requires an explicit decision on the named gap."),
        ("BLOCK", "Do not approve until the named requirement is satisfied."),
    ],
)
def test_manager_view_has_bounded_approval_guidance(
    verdict: str, expected: str
) -> None:
    record = _record()
    record["verdict"] = verdict
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    record["record_digest"] = canonical.digest(payload)

    diag = diagnose(record)
    text, intact = render_html(record)

    assert intact
    assert diag["manager_view"]["approval"] == expected
    assert expected in text
    assert "Manager / auditor view" in text
    assert "Residual risk" in text
    assert "safe to approve" not in text.lower()


def test_manager_pass_retains_scope_boundary() -> None:
    record = _record()
    record["verdict"] = "PASS"
    record["reasons"] = []
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    record["record_digest"] = canonical.digest(payload)

    diag = diagnose(record)

    assert "Normal code and product review still apply" in (
        diag["manager_view"]["approval"]
    )
    assert "risk outside that policy remains" in (
        diag["manager_view"]["residual_risk"]
    )


def test_manager_pass_names_an_accepted_risk_exception() -> None:
    record = _record()
    record["verdict"] = "PASS"
    record["reasons"] = [
        {
            "rule": "advisory_warning",
            "severity": "PASS",
            "source_id": "scanner.sarif",
            "detail": "accepted scanner finding",
            "accepted_risk": {
                "selector": "advisory_warning@scanner.sarif",
                "justification": "Reviewed by the policy owner",
                "original_severity": "WARN",
            },
        }
    ]
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    record["record_digest"] = canonical.digest(payload)

    diag = diagnose(record)

    assert "passed with 1 recorded accepted-risk exception" in (
        diag["manager_view"]["approval"]
    )
    assert diag["manager_view"]["action_owner"] == "Policy owner"


def test_manager_pass_with_no_required_control_makes_no_recommendation() -> None:
    record = _record()
    record["verdict"] = "PASS"
    record["reasons"] = []
    record["observation"] = {
        **record.get("observation", {}),
        "github_baseline": "no_required_checks",
    }
    for source in record["inputs"]:
        source["required"] = False
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    record["record_digest"] = canonical.digest(payload)

    diag = diagnose(record)

    assert diag["manager_view"]["approval"] == (
        "No approval recommendation: this policy required no controls."
    )
    assert "no required status checks" in (
        diag["manager_view"]["control_status"].lower()
    )
    assert diag["manager_view"]["action_owner"] == "Repository administrator"


def test_manager_view_assigns_operational_owner() -> None:
    record = _record()
    record["verdict"] = "BLOCK"
    record["reasons"] = [
        {
            "rule": "missing_required_source",
            "severity": "BLOCK",
            "source_id": "ci / test",
            "detail": "required check is missing",
            "state": "missing",
        }
    ]
    record["inputs"] = []
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    record["record_digest"] = canonical.digest(payload)

    diag = diagnose(record)

    assert diag["manager_view"] == {
        "approval": "Do not approve until the named requirement is satisfied.",
        "control_status": "Required check 'ci / test' did not run for this commit.",
        "residual_risk": (
            "The protection expected from this control was not applied to this "
            "commit."
        ),
        "action_owner": "Owner of the named check or workflow",
    }


def test_manager_view_rejects_tampered_record() -> None:
    record = _record()
    record["verdict"] = "PASS"

    diag = diagnose(record)
    text, intact = render_html(record)

    assert not intact
    assert diag["manager_view"]["approval"].startswith("Do not approve")
    assert "AOS integration owner" in text


def test_html_escapes_hostile_values() -> None:
    record = _record()
    record["inputs"][0]["id"] = '<script>alert(1)</script>"onload'
    payload = {k: v for k, v in record.items() if k != "record_digest"}
    record["record_digest"] = canonical.digest(payload)
    text, intact = render_html(record)
    assert intact
    assert "<script>alert" not in text
    assert "&lt;script&gt;" in text


def test_html_is_print_ready_without_changing_the_evidence_model() -> None:
    text, _ = render_html(_record())
    assert "@media print" in text
    assert "break-inside:avoid" in text


def test_html_flags_tampered_record() -> None:
    record = _record()
    record["verdict"] = "PASS" if record["verdict"] != "PASS" else "WARN"
    text, intact = render_html(record)
    assert not intact
    assert "Do not trust this record" in text


def test_verify_bindings_and_cli_flags(tmp_path: Path) -> None:
    from aos_workflow_gate.summarize import verify_bindings

    record = _record()
    bundle = json.loads(
        (ROOT / "examples" / "github-pr-signal-bundle.json").read_text(
            encoding="utf-8"
        )
    )
    policy_path = ROOT / "policies" / "default.yml"
    bindings = verify_bindings(record, bundle=bundle, policy_path=policy_path)
    assert bindings == {
        "bundle_binding": "OK",
        "policy_binding": "OK",
        "semantic_replay": "OK",
    }
    text, _ = render_html(record, bindings)
    assert "Semantic replay" in text and "Policy binding" in text

    # a swapped bundle fails the binding and the exit code
    other = dict(bundle, subject=dict(bundle["subject"], sha="9" * 40))
    assert verify_bindings(record, bundle=other)["bundle_binding"] == (
        "FAILED"
    )
    bundle_path = tmp_path / "other-bundle.json"
    # Even a re-digested pair fails when record and bundle subjects differ.
    rebound = dict(record)
    rebound["input_bundle_digest"] = canonical.digest(other)
    rebound.pop("record_digest", None)
    rebound["record_digest"] = canonical.digest(rebound)
    assert verify_bindings(rebound, bundle=other)["bundle_binding"] == (
        "FAILED"
    )
    bundle_path.write_text(json.dumps(other), encoding="utf-8")
    assert (
        main(
            [
                "summarize",
                "--input",
                str(ROOT / "examples" / "gate-decision.json"),
                "--html",
                "--bundle",
                str(bundle_path),
                "--policy",
                str(policy_path),
                "--out",
                str(tmp_path / "e.html"),
            ]
        )
        == 1
    )
    assert "FAILED" in (tmp_path / "e.html").read_text(encoding="utf-8")


def test_cli_html_out(tmp_path: Path) -> None:
    out = tmp_path / "evidence.html"
    assert (
        main(
            [
                "summarize",
                "--input",
                str(ROOT / "examples" / "gate-decision.json"),
                "--html",
                "--out",
                str(out),
            ]
        )
        == 0
    )
    text = out.read_text(encoding="utf-8")
    assert text.startswith("<!doctype html>")
    golden = (GOLDEN / "gate-decision.html").read_text(encoding="utf-8")
    assert text == golden
