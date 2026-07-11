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

from aos_workflow_gate import canonical
from aos_workflow_gate.summarize import diagnose, render_html, render_markdown


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
        "inputs": inputs
        or [
            {
                "id": "ci",
                "kind": "github_check",
                "status": "success",
                "required": True,
                "digest": None,
                "signal_source": None,
            }
        ],
        "input_bundle_digest": "sha256:" + "1" * 64,
    }
    if observation is not None:
        record["observation"] = observation
    record["record_digest"] = canonical.digest(record)
    return record


def _reason(
    rule: str, severity: str, source_id: str | None, detail: str = "d"
) -> dict[str, Any]:
    return {
        "rule": rule,
        "severity": severity,
        "source_id": source_id,
        "detail": detail,
    }


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
    assert "…and 2 more reason(s)" in text
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
