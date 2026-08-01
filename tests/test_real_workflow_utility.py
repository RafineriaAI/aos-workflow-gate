from __future__ import annotations

from tools.real_workflow_utility import (
    _message_structure,
    _naive_alert,
    _naive_source_alert,
    _problem_scope,
    _rate,
)


def test_naive_baseline_alerts_on_every_non_success_state() -> None:
    assert not _naive_alert([{"status": "completed", "conclusion": "success"}])
    assert _naive_alert([{"status": "completed", "conclusion": "skipped"}])
    assert _naive_alert([{"status": "in_progress", "conclusion": None}])


def test_same_snapshot_naive_baseline_uses_check_and_status_sources() -> None:
    assert _naive_source_alert([{"kind": "github_check", "status": "skipped"}])
    assert not _naive_source_alert(
        [
            {"kind": "github_check", "status": "success"},
            {"kind": "branch_rules_summary", "status": "failure"},
        ]
    )


def test_problem_scope_separates_workflow_control_from_code_change() -> None:
    assert _problem_scope("missing_required_source") == (
        "workflow_or_repository_control"
    )
    assert _problem_scope("project_test_failed") == "code_or_project_change"
    assert _problem_scope(None) == "none"


def test_non_pass_message_requires_every_user_facing_field() -> None:
    complete = {
        "verdict": "WARN",
        "problem": "Named problem",
        "impact": "Named impact",
        "affected_area": "Named check",
        "next": "Run the named check",
        "severity": "WARN",
    }
    assert _message_structure(complete)
    assert not _message_structure({**complete, "next": ""})
    assert _message_structure({"verdict": "PASS"})


def test_rate_does_not_invent_a_value_without_a_denominator() -> None:
    assert _rate(0, 0) == {"numerator": 0, "denominator": 0, "rate": None}
