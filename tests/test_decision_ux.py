"""Scope-aware low-noise decision UX.

One projection — ``diagnose(record)`` — feeds every renderer, so the
CLI, the Action step summary, and the HTML evidence view cannot drift
in substance. These tests pin the 30-second contract: scope, freshness,
and effect are always stated; at most three gaps are itemized with one
dominant problem; an enforceably clean PASS is quiet; and untrusted
values stay escaped in both views.
"""

from __future__ import annotations

from typing import Any

import pytest

from aos_workflow_gate import canonical
from aos_workflow_gate.summarize import (
    diagnose,
    render_github_annotation,
    render_html,
    render_markdown,
)


def _record(
    *,
    verdict: str = "PASS",
    reasons: list[dict[str, Any]] | None = None,
    inputs: list[dict[str, Any]] | None = None,
    observation: dict[str, Any] | None = None,
    can_block: bool = False,
    repository: str = "octo/repo",
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "schema_version": "aos-workflow-gate-decision/v0",
        "generator": {"tool": "aos-workflow-gate", "version": "0.0.0"},
        "subject": {
            "repository": repository,
            "ref": None,
            "sha": "c" * 40,
            "pull_request": None,
        },
        "policy": {
            "policy_id": "test",
            "mode": "advisory",
            "verification_status": "UNSIGNED_NOT_OFFICIAL",
            "digest": "sha256:" + "0" * 64,
        },
        "verdict": verdict,
        "can_block": can_block,
        "verification_status": "UNSIGNED_NOT_OFFICIAL",
        "summary": f"Gate {verdict}: test.",
        "reasons": reasons or [],
        "inputs": (
            inputs
            if inputs is not None
            else [
                {
                    "id": "ci",
                    "kind": "github_check",
                    "status": "success",
                    "required": True,
                    "digest": None,
                    "signal_source": None,
                }
            ]
        ),
        "input_bundle_digest": "sha256:" + "1" * 64,
    }
    if observation is not None:
        record["observation"] = observation
    record["record_digest"] = canonical.digest(record)
    return record


def _reason(
    rule: str,
    severity: str,
    source_id: str | None,
    detail: str = "d",
    *,
    state: str | None = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "rule": rule,
        "severity": severity,
        "source_id": source_id,
        "detail": detail,
    }
    if state is not None:
        value["state"] = state
    return value


# --- quiet PASS ------------------------------------------------------------


def test_quiet_pass_has_no_tables() -> None:
    text, intact = render_markdown(_record())
    assert intact
    assert "**Scope:**" in text
    assert "**Freshness:**" in text
    assert "**Effect:**" in text
    assert "self-check OK" in text
    assert "| Field | Value |" not in text
    assert "### Inputs" not in text
    assert len(text.splitlines()) <= 12


def test_github_semantics_counts_skipped_required_as_satisfied() -> None:
    record = _record(
        inputs=[
            {
                "id": "ci",
                "kind": "github_check",
                "status": "skipped",
                "required": True,
                "digest": None,
                "signal_source": None,
            }
        ],
        observation={"github_baseline": "clear"},
    )
    record["policy"]["required_status_semantics"] = "github"
    record["record_digest"] = canonical.digest(
        {key: value for key, value in record.items() if key != "record_digest"}
    )

    diag = diagnose(record)

    assert diag["counts"]["required_successful"] == 1
    assert diag["finding"].startswith(
        "Every required check satisfied GitHub's merge semantics"
    )


def test_decision_contrast_separates_native_and_aos_only_gaps() -> None:
    native = _record(
        verdict="BLOCK",
        reasons=[
            _reason(
                "missing_required_source",
                "BLOCK",
                "ci",
                state="pending",
            )
        ],
        inputs=[],
        observation={"github_baseline": "waiting"},
    )
    aos_only = _record(
        verdict="WARN",
        reasons=[
            _reason("non_independent_evidence", "WARN", None)
        ],
        observation={"github_baseline": "clear"},
    )

    native_diag = diagnose(native)
    aos_diag = diagnose(aos_only)

    assert native_diag["contrast"]["code"] == "github_already_blocks"
    assert native_diag["contrast"]["incremental"] is False
    assert aos_diag["contrast"]["code"] == "aos_policy_gap"
    assert aos_diag["contrast"]["incremental"] is True
    markdown, _ = render_markdown(aos_only)
    assert "**Decision contrast:**" in markdown


def test_zero_required_pass_is_coverage_fact_not_alert() -> None:
    record = _record(
        reasons=[_reason("no_required_sources", "PASS", None)],
        inputs=[],
        observation={"github_baseline": "no_required_checks"},
    )

    diag = diagnose(record)

    assert diag["verdict"] == "PASS"
    assert diag["gaps_total"] == 0
    assert "without raising a per-PR alert" in diag["finding"]
    assert diag["contrast"]["code"] == "github_no_required_gate"


def test_pass_with_zero_required_is_not_quiet() -> None:
    """Zero-required PASS keeps the full view: the coverage suggestion
    is the funnel out of the decision gap and must not disappear."""
    record = _record(
        inputs=[
            {
                "id": "ci", "kind": "github_check", "status": "success",
                "required": False, "digest": None, "signal_source": None,
            }
        ]
    )
    text, _ = render_markdown(record)
    assert "### Coverage" in text
    assert "Decision gap" in text


def test_warn_and_block_keep_the_full_view() -> None:
    record = _record(
        verdict="WARN",
        reasons=[_reason("advisory_warning", "WARN", "scan")],
    )
    text, _ = render_markdown(record)
    assert "| Field | Value |" in text
    assert "### Top gaps" in text


def test_pass_level_advisory_observation_stays_quiet() -> None:
    record = _record(
        reasons=[_reason("advisory_warning", "PASS", "scan")],
        inputs=[
            {
                "id": "ci",
                "kind": "github_check",
                "status": "success",
                "required": True,
                "digest": None,
                "signal_source": None,
            },
            {
                "id": "scan",
                "kind": "github_check",
                "status": "skipped",
                "required": False,
                "digest": None,
                "signal_source": None,
            },
        ],
    )

    diag = diagnose(record)
    text, _ = render_markdown(record)

    assert diag["gaps_total"] == 0
    assert diag["counts"]["advisory_warnings"] == 0
    assert "Every required check AOS evaluated" in diag["finding"]
    assert "### Technical evidence" not in text


def test_plain_finding_names_zero_required_github_gap() -> None:
    record = _record(
        verdict="WARN",
        reasons=[_reason("no_required_sources", "WARN", None)],
        inputs=[],
        observation={"github_baseline": "no_required_checks"},
    )

    diag = diagnose(record)
    text, _ = render_markdown(record)

    assert diag["finding"] == (
        "GitHub has no required status checks for this branch, so green "
        "checks do not enforce a merge gate."
    )
    assert "**What AOS found:**" in text
    assert diag["finding"] in text


def test_plain_finding_explains_self_validating_workflow() -> None:
    record = _record(
        verdict="WARN",
        reasons=[
            _reason("non_independent_evidence", "WARN", None)
        ],
    )

    assert diagnose(record)["finding"] == (
        "This PR changed a workflow that also produced checks used to "
        "assess the same PR."
    )


def test_sarif_warning_has_specific_finding_and_next_action() -> None:
    record = _record(
        verdict="WARN",
        reasons=[
            _reason(
                "advisory_warning",
                "WARN",
                "sarif.zizmor",
                "advisory source status is 'warning'; SARIF: 2 findings",
            )
        ],
        inputs=[
            {
                "id": "sarif.zizmor",
                "kind": "sarif_summary",
                "status": "warning",
                "required": False,
                "digest": None,
                "signal_source": "sarif_file",
            }
        ],
    )

    diag = diagnose(record)

    assert diag["finding"] == (
        "Scanner evidence 'sarif.zizmor' contains findings that need review."
    )
    assert diag["remediation"]["code"] == "review_sarif_findings"
    assert "SARIF findings" in diag["next"]


def test_github_annotation_is_nonblocking_and_command_safe() -> None:
    source = "ci%0A::error injected\r\n"
    record = _record(
        verdict="BLOCK",
        reasons=[
            _reason(
                "missing_required_source",
                "BLOCK",
                source,
                state="missing",
            )
        ],
        inputs=[],
    )

    annotation = render_github_annotation(record)

    assert annotation is not None
    assert annotation.startswith(
        "::warning title=AOS BLOCK (non-blocking)::"
    )
    assert "%250A" in annotation
    assert "\n" not in annotation
    assert "\r" not in annotation
    assert "Next:" in annotation


def test_enforced_block_uses_error_annotation() -> None:
    record = _record(
        verdict="BLOCK",
        can_block=True,
        reasons=[_reason("missing_required_source", "BLOCK", "ci")],
        inputs=[],
    )
    annotation = render_github_annotation(record)
    assert annotation is not None
    assert annotation.startswith("::error title=AOS BLOCK (enforced)::")


def test_pass_emits_no_github_annotation() -> None:
    assert render_github_annotation(_record()) is None


# --- gaps: at most three, ranked, one dominant -----------------------------


def test_gaps_capped_at_three_with_remainder() -> None:
    reasons = [
        _reason("advisory_warning", "WARN", f"scan-{i}") for i in range(4)
    ] + [_reason("failed_required_source", "BLOCK", "ci", "required failed")]
    record = _record(verdict="BLOCK", reasons=reasons)
    diag = diagnose(record)
    assert diag["gaps_total"] == 5
    assert len(diag["gaps"]) == 3
    # severity dominates: the blocking gap ranks first
    assert diag["gaps"][0]["rule"] == "failed_required_source"
    assert diag["dominant"] == "'ci': required failed"
    text, _ = render_markdown(record)
    assert "**Dominant problem:**" in text
    assert "...and 2 more reason(s)" in text
    # only the top three are itemized
    assert text.count("- WARN") == 2


def test_single_gap_needs_no_dominant_banner() -> None:
    record = _record(
        verdict="WARN",
        reasons=[_reason("advisory_warning", "WARN", "scan")],
    )
    text, _ = render_markdown(record)
    assert "**Dominant problem:**" not in text
    assert "### Top gaps" in text


def test_gap_ranking_is_stable_and_severity_first() -> None:
    reasons = [
        _reason("no_required_sources", "WARN", None),
        _reason("incomplete_collection", "WARN", None),
        _reason("missing_required_source", "BLOCK", "b"),
        _reason("missing_required_source", "BLOCK", "a"),
    ]
    diag = diagnose(_record(verdict="BLOCK", reasons=reasons))
    ordered = [
        (gap["rule"], gap.get("source_id")) for gap in diag["gaps"]
    ]
    assert ordered == [
        ("missing_required_source", "a"),
        ("missing_required_source", "b"),
        ("incomplete_collection", None),
    ]


# --- scope, freshness, effect ----------------------------------------------


def test_scope_names_subject_and_boundary() -> None:
    diag = diagnose(_record())
    assert "octo/repo@cccccccccccc" in diag["scope"]
    assert "not full merge-readiness" in diag["scope"]


def test_freshness_from_observation() -> None:
    record = _record(
        observation={
            "status": "complete",
            "observed_at": "2026-07-11T10:00:00Z",
            "workflow_visibility": {
                "available": True,
                "units_total": 3,
                "not_started": 1,
                "action_required": 1,
            },
        }
    )
    diag = diagnose(record)
    assert "observed 2026-07-11T10:00:00Z" in diag["freshness"]
    assert "collection complete" in diag["freshness"]
    assert "1 workflow unit(s) had not started" in diag["freshness"]


def test_freshness_honest_when_unrecorded() -> None:
    diag = diagnose(_record())
    assert "not recorded" in diag["freshness"]


def test_effect_states_enforcement() -> None:
    assert diagnose(_record())["effect"].startswith("advisory")
    assert diagnose(_record(can_block=True))["effect"].startswith(
        "enforcing"
    )


def test_scope_shows_protection_source_and_strict() -> None:
    record = _record(
        observation={
            "status": "complete",
            "protection_source": "rulesets+classic_branch_protection",
            "strict_up_to_date_required": True,
        }
    )
    diag = diagnose(record)
    assert "rulesets+classic_branch_protection" in diag["scope"]
    assert "up to date" in diag["scope"]


# --- state-precise remediation ---------------------------------------------


@pytest.mark.parametrize(
    ("state", "code", "count_key"),
    [
        ("missing", "required_source_missing", "required_missing"),
        ("pending", "required_source_pending", "required_pending"),
        (
            "unverifiable",
            "required_source_unverifiable",
            "required_unverifiable",
        ),
    ],
)
def test_required_gap_remediation_uses_structural_state(
    state: str, code: str, count_key: str
) -> None:
    reason = _reason(
        "missing_required_source",
        "BLOCK",
        "ci",
        "opaque display text",
        state=state,
    )

    diag = diagnose(_record(verdict="BLOCK", reasons=[reason], inputs=[]))

    assert diag["remediation"]["code"] == code
    assert diag["remediation"]["state"] == state
    assert diag["remediation"]["source_id"] == "ci"
    assert diag["counts"]["required_total"] == 1
    assert diag["counts"]["advisory_total"] == 0
    assert diag["counts"][count_key] == 1
    assert "1 required" in diag["scope"]
    assert diag["gaps"][0]["remediation"] == diag["remediation"]
    assert diag["next"] == diag["remediation"]["action"]


def test_legacy_detail_is_never_parsed_as_operational_state() -> None:
    reason = _reason(
        "missing_required_source",
        "BLOCK",
        "ci",
        "display only (requirement state: pending)",
    )

    diag = diagnose(_record(verdict="BLOCK", reasons=[reason], inputs=[]))

    assert diag["remediation"]["code"] == "required_source_unclassified"
    assert "state" not in diag["remediation"]
    assert diag["counts"]["required_missing"] == 1
    assert diag["counts"]["required_pending"] == 0


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("failure", "required_source_failed"),
        ("cancelled", "required_source_cancelled"),
        ("timed_out", "required_source_timed_out"),
        ("skipped", "required_source_skipped"),
        ("neutral", "required_source_neutral"),
        ("action_required", "required_source_action_required"),
        ("stale", "required_source_stale"),
        ("startup_failure", "required_source_startup_failure"),
        ("tampered", "required_source_tampered"),
        ("subject_mismatch", "required_source_subject_mismatch"),
        ("bounded_duplicate", "required_source_bounded_duplicate"),
        ("freshness_unverified", "required_source_freshness_unverified"),
    ],
)
def test_failed_check_remediation_uses_structured_input_status(
    status: str, code: str
) -> None:
    inputs = [
        {
            "id": "ci",
            "kind": "github_check",
            "status": status,
            "required": True,
            "digest": None,
            "signal_source": None,
        }
    ]
    reason = _reason(
        "failed_required_source",
        "BLOCK",
        "ci",
        "same display text for every status",
    )

    diag = diagnose(
        _record(verdict="BLOCK", reasons=[reason], inputs=inputs)
    )

    assert diag["remediation"]["code"] == code
    assert diag["remediation"]["state"] == status
    assert "ci" in diag["next"]


@pytest.mark.parametrize(
    ("status", "code"),
    [
        ("wait_timeout", "collection_wait_timeout"),
        ("subject_mismatch", "collection_subject_mismatch"),
        ("truncated", "collection_truncated"),
    ],
)
def test_collection_remediation_uses_structured_observation_status(
    status: str, code: str
) -> None:
    reason = _reason(
        "incomplete_collection",
        "WARN",
        None,
        "same display text for every collection status",
    )

    diag = diagnose(
        _record(
            verdict="WARN",
            reasons=[reason],
            observation={"status": status},
        )
    )

    assert diag["remediation"]["code"] == code
    assert diag["remediation"]["state"] == status
# --- one projection, two views ----------------------------------------------


def test_markdown_and_html_share_the_same_diagnosis() -> None:
    record = _record(
        verdict="WARN",
        reasons=[_reason("advisory_warning", "WARN", "scan")],
        observation={"status": "complete",
                     "observed_at": "2026-07-11T10:00:00Z"},
    )
    import html as html_module

    diag = diagnose(record)
    markdown, _ = render_markdown(record)
    html, _ = render_html(record)
    assert diag["freshness"] in markdown.replace("\\", "")
    assert html_module.escape(diag["freshness"], quote=True) in html
    assert diag["next"] in markdown.replace("\\", "")
    assert html_module.escape(diag["next"], quote=True) in html


# --- safe escaping -----------------------------------------------------------


def test_untrusted_values_stay_escaped_in_both_views() -> None:
    hostile = 'repo|<script>alert(1)</script>`*_'
    record = _record(
        verdict="WARN",
        repository=hostile,
        reasons=[
            _reason(
                "advisory_warning", "WARN",
                "bad|id`", "detail <img src=x onerror=1> | pipe",
            )
        ],
    )
    markdown, _ = render_markdown(record)
    assert "<script>" not in markdown
    assert "\\|" in markdown  # pipes neutralized for tables
    html, _ = render_html(record)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
    assert "onerror=1&gt;" in html or "&lt;img" in html
