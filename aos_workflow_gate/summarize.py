"""Markdown summary rendering for decision records.

``summarize`` turns a decision record into a compact Markdown block for
maintainers, for example a GitHub Actions step summary. It re-checks the
record's self-digest so a tampered record is visibly flagged instead of being
summarized as if it were trustworthy.
"""

from __future__ import annotations

from typing import Any

from .errors import InputError
from .evidence import verify_record

VERDICTS = ("PASS", "WARN", "BLOCK")

REPAIR_HINTS = {
    "missing_required_source": (
        "no completed check run with this exact name was found on the "
        "commit; verify the name or wait for the check to finish, then "
        "re-run the gate"
    ),
    "failed_required_source": (
        "the required check did not conclude success; fix or re-run it, "
        "then re-evaluate"
    ),
    "advisory_warning": (
        "advisory findings warn but never block; review the source's own "
        "report and decide"
    ),
    "malformed_input": (
        "the signal bundle does not match schema draft-0; compare with "
        "examples/github-pr-signal-bundle.json"
    ),
}


def render_markdown(record: Any) -> tuple[str, bool]:
    """Render a decision record as Markdown.

    Returns the Markdown text and whether the record's self-digest check
    passed. Raises :class:`InputError` when the value is not a decision
    record at all.
    """
    if not isinstance(record, dict):
        raise InputError("decision record must be a JSON object")
    verdict = record.get("verdict")
    if verdict not in VERDICTS:
        raise InputError("decision record has no valid verdict")

    intact = verify_record(record)
    subject = _dict_field(record, "subject")
    policy = _dict_field(record, "policy")

    lines: list[str] = [f"## Gate decision: {verdict}", ""]
    summary = record.get("summary")
    if isinstance(summary, str) and summary:
        lines += [summary, ""]
    if not intact:
        lines += [
            "> **Warning:** record content does not match its self-digest. "
            "Do not trust this record.",
            "",
        ]

    lines += ["| Field | Value |", "| --- | --- |"]
    lines += _subject_rows(subject)
    policy_id = policy.get("policy_id", "-")
    mode = policy.get("mode", "-")
    lines.append(f"| Policy | `{policy_id}` ({mode}) |")
    lines.append(f"| Policy digest | `{policy.get('digest', '-')}` |")
    lines.append(
        f"| Input bundle digest | `{record.get('input_bundle_digest', '-')}` |"
    )
    lines.append(f"| Record digest | `{record.get('record_digest', '-')}` |")
    lines.append(f"| Record self-check | {'OK' if intact else 'FAILED'} |")
    lines.append(
        f"| Verification status | {record.get('verification_status', '-')} |"
    )
    lines.append("")

    reasons = record.get("reasons")
    if isinstance(reasons, list) and reasons:
        lines += ["### Reasons", ""]
        for reason in reasons:
            if isinstance(reason, dict):
                severity = reason.get("severity", "-")
                rule = reason.get("rule", "-")
                source = reason.get("source_id") or "-"
                detail = reason.get("detail", "")
                lines.append(f"- {severity} `{rule}` {source}: {detail}")
                hint = REPAIR_HINTS.get(str(rule))
                if hint:
                    lines.append(f"  - Hint: {hint}")
        lines.append("")

    inputs = record.get("inputs")
    if isinstance(inputs, list) and inputs:
        lines += [
            "### Inputs",
            "",
            "| Id | Kind | Required | Status |",
            "| --- | --- | --- | --- |",
        ]
        for source in inputs:
            if isinstance(source, dict):
                required = "yes" if source.get("required") else "no"
                lines.append(
                    f"| {_cell(source.get('id', '-'))} "
                    f"| {_cell(source.get('kind', '-'))} "
                    f"| {required} | {_cell(source.get('status', '-'))} |"
                )
        lines.append("")
        lines += _coverage_lines(inputs)

    return "\n".join(lines), intact


def _coverage_lines(inputs: list[Any]) -> list[str]:
    sources = [source for source in inputs if isinstance(source, dict)]
    required = [source for source in sources if source.get("required")]
    lines = [
        "### Coverage",
        "",
        f"- Required sources: {len(required)} of {len(sources)}",
    ]
    if not required:
        lines.append(
            "- Decision gap: no source is required, so a missing or failed "
            "check cannot make this gate BLOCK. The record is evidence, "
            "not enforcement."
        )
    else:
        required_ids = ", ".join(
            f"`{source.get('id', '-')}`" for source in required
        )
        lines.append(f"- Blocking on: {required_ids}")
    lines.append("")
    return lines


def _cell(value: Any) -> str:
    """Make a value safe inside a Markdown table cell (old-web friendly)."""
    text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")


def _dict_field(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def _subject_rows(subject: dict[str, Any]) -> list[str]:
    rows = [f"| Repository | {_cell(subject.get('repository', '-'))} |"]
    if subject.get("ref"):
        rows.append(f"| Ref | `{_cell(subject['ref'])}` |")
    rows.append(f"| Commit | `{subject.get('sha', '-')}` |")
    if subject.get("pull_request") is not None:
        rows.append(f"| Pull request | #{subject['pull_request']} |")
    return rows
