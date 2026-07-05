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
        lines += [_escape(summary), ""]
    if not intact:
        lines += [
            "> **Warning:** record content does not match its self-digest. "
            "Do not trust this record.",
            "",
        ]

    lines += ["| Field | Value |", "| --- | --- |"]
    lines += _subject_rows(subject)
    policy_id = _code(policy.get("policy_id", "-"))
    mode = _escape(policy.get("mode", "-"))
    lines.append(f"| Policy | {policy_id} ({mode}) |")
    lines.append(f"| Policy digest | {_code(policy.get('digest', '-'))} |")
    lines.append(
        "| Input bundle digest | "
        f"{_code(record.get('input_bundle_digest', '-'))} |"
    )
    lines.append(f"| Record digest | {_code(record.get('record_digest', '-'))} |")
    lines.append(f"| Record self-check | {'OK' if intact else 'FAILED'} |")
    lines.append(
        f"| Can block this job | {'yes' if record.get('can_block') else 'no'} |"
    )
    lines.append(
        "| Verification status | "
        f"{_escape(record.get('verification_status', '-'))} |"
    )
    lines.append("")

    reasons = record.get("reasons")
    if isinstance(reasons, list) and reasons:
        lines += ["### Reasons", ""]
        for reason in reasons:
            if isinstance(reason, dict):
                severity = _escape(reason.get("severity", "-"))
                rule = reason.get("rule", "-")
                source = _escape(reason.get("source_id") or "-")
                detail = _escape(reason.get("detail", ""))
                lines.append(f"- {severity} {_code(rule)} {source}: {detail}")
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
                    f"| {_escape(source.get('id', '-'))} "
                    f"| {_escape(source.get('kind', '-'))} "
                    f"| {required} | {_escape(source.get('status', '-'))} |"
                )
        lines.append("")
        lines += _coverage_lines(inputs)
        if inputs and not record.get("can_block"):
            required_any = any(
                isinstance(s, dict) and s.get("required") for s in inputs
            )
            if required_any:
                lines += [
                    "- Advisory only: a BLOCK verdict would not fail the "
                    "job (no enforcement configured).",
                    "",
                ]

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
            _code(source.get("id", "-")) for source in required
        )
        lines.append(f"- Blocking on: {required_ids}")
    lines.append("")
    return lines


_ESCAPE_CHARS = "\\`*_[]<>|"


def _escape(value: Any) -> str:
    """Neutralize Markdown in an untrusted value used as plain text.

    Source ids and statuses can be attacker-influenced (for example a fork
    pull request can rename a job), so links, emphasis, HTML, code spans,
    and table breaks are all escaped before the value reaches a summary.
    """
    text = str(value).replace("\r", " ").replace("\n", " ")
    for ch in _ESCAPE_CHARS:
        text = text.replace(ch, "\\" + ch)
    return text


def _code(value: Any) -> str:
    """Render an untrusted value as an inline code span, safely."""
    text = str(value).replace("\r", " ").replace("\n", " ")
    text = text.replace("`", "'")
    return f"`{text}`"


def _dict_field(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def _subject_rows(subject: dict[str, Any]) -> list[str]:
    rows = [f"| Repository | {_escape(subject.get('repository', '-'))} |"]
    if subject.get("ref"):
        rows.append(f"| Ref | {_code(subject['ref'])} |")
    rows.append(f"| Commit | {_code(subject.get('sha', '-'))} |")
    if subject.get("pull_request") is not None:
        rows.append(f"| Pull request | #{_escape(subject['pull_request'])} |")
    return rows
