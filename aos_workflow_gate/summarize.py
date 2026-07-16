"""Markdown and static-HTML rendering for decision records.

``summarize`` turns a decision record into a compact Markdown block for
maintainers (for example a GitHub Actions step summary) or, with
``--html``, into a deterministic, self-contained static HTML evidence
view. Both renderers consume the same :func:`diagnose` result, so they
cannot drift in substance. Every view re-checks the record's
self-digest so a tampered record is visibly flagged instead of being
summarized as if it were trustworthy.
"""

from __future__ import annotations

import html as _html
from pathlib import Path
from typing import Any

from . import canonical
from .errors import InputError
from .evaluate import evaluate
from .evidence import subject_identity, verify_record
from .policy import load_policy

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
    "no_required_sources": (
        "nothing is required, so nothing can block; name required "
        "checks (see the suggestion under Coverage) to close the "
        "decision gap"
    ),
    "malformed_input": (
        "the signal bundle does not match schema draft-0; compare with "
        "examples/github-pr-signal-bundle.json"
    ),
    "incomplete_collection": (
        "the collection did not observe everything that may exist for "
        "this commit; re-collect with a larger wait/API budget, or "
        "accept the record as evidence of a bounded observation"
    ),
    "non_independent_evidence": (
        "the named checks were produced by a workflow this change "
        "modifies; require evidence from a verifier governed outside "
        "the change"
    ),
    "verifier_change_unavailable": (
        "the verifier-change analysis was incomplete; grant the named "
        "read permission, remove the collection error, and re-run"
    ),
}


def diagnose(record: Any) -> dict[str, Any]:
    """One shared diagnosis consumed by every renderer.

    Computes the verdict, integrity, signal counts, and the single
    dominant next step from a decision record, so different views
    (Markdown, HTML) cannot drift in what they say — only in how they
    show it. Raises :class:`InputError` when the value is not a
    decision record at all.
    """
    if not isinstance(record, dict):
        raise InputError("decision record must be a JSON object")
    verdict = record.get("verdict")
    if verdict not in VERDICTS:
        raise InputError("decision record has no valid verdict")

    intact = verify_record(record)
    inputs = [
        source for source in record.get("inputs", [])
        if isinstance(source, dict)
    ] if isinstance(record.get("inputs"), list) else []
    reasons = [
        reason for reason in record.get("reasons", [])
        if isinstance(reason, dict)
    ] if isinstance(record.get("reasons"), list) else []
    required = [source for source in inputs if source.get("required")]

    def _requirement_state(reason: dict[str, Any]) -> str:
        detail = str(reason.get("detail", ""))
        for state in ("pending", "unverifiable"):
            if f"(requirement state: {state})" in detail:
                return state
        return "missing"

    missing_reasons = [
        reason for reason in reasons
        if reason.get("rule") == "missing_required_source"
    ]
    counts = {
        "required_total": len(required),
        "required_successful": sum(
            1 for source in required
            if str(source.get("status", "")).lower() == "success"
        ),
        "required_failed": sum(
            1 for reason in reasons
            if reason.get("rule") == "failed_required_source"
        ),
        "required_missing": sum(
            1 for reason in missing_reasons
            if _requirement_state(reason) == "missing"
        ),
        "required_pending": sum(
            1 for reason in missing_reasons
            if _requirement_state(reason) == "pending"
        ),
        "required_unverifiable": sum(
            1 for reason in missing_reasons
            if _requirement_state(reason) == "unverifiable"
        ),
        "advisory_total": len(inputs) - len(required),
        "advisory_warnings": sum(
            1 for reason in reasons if reason.get("severity") == "WARN"
        ),
        "blocking_reasons": sum(
            1 for reason in reasons if reason.get("severity") == "BLOCK"
        ),
        "decision_gap": any(
            reason.get("rule") == "no_required_sources"
            for reason in reasons
        ),
    }
    observation = _dict_field(record, "observation")
    gaps = _rank_gaps(reasons)
    return {
        "verdict": verdict,
        "intact": intact,
        "summary": record.get("summary"),
        "can_block": bool(record.get("can_block")),
        "counts": counts,
        "next": _next_step(record, intact),
        "scope": _scope_statement(record, observation),
        "freshness": _freshness_statement(observation),
        "effect": _effect_statement(record),
        "gaps": gaps[:3],
        "gaps_total": len(gaps),
        "dominant": _dominant_problem(gaps),
        "observation": observation,
        "subject": _dict_field(record, "subject"),
        "policy": _dict_field(record, "policy"),
        "reasons": reasons,
        "inputs": inputs,
        "record_digest": record.get("record_digest"),
        "input_bundle_digest": record.get("input_bundle_digest"),
        "verification_status": record.get("verification_status"),
    }


_GAP_RULE_RANK = {
    "malformed_input": 0,
    "missing_required_source": 1,
    "failed_required_source": 1,
    "verifier_change_unavailable": 2,
    "non_independent_evidence": 2,
    "incomplete_collection": 3,
    "advisory_warning": 4,
    "no_required_sources": 5,
}
_SEVERITY_RANK = {"BLOCK": 0, "WARN": 1, "PASS": 2}


def _rank_gaps(reasons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every reason, ranked most-decision-relevant first.

    Severity dominates (a blocking gap always outranks a warning), then
    the rule's diagnostic priority, then the source id for a stable
    order. The projection keeps the full count but shows at most three.
    """
    def key(reason: dict[str, Any]) -> tuple[int, int, str]:
        return (
            _SEVERITY_RANK.get(str(reason.get("severity")), 9),
            _GAP_RULE_RANK.get(str(reason.get("rule")), 9),
            str(reason.get("source_id") or ""),
        )

    return sorted(reasons, key=key)


def _dominant_problem(gaps: list[dict[str, Any]]) -> str | None:
    """One sentence naming the problem that decides this record."""
    if not gaps:
        return None
    gap = gaps[0]
    source = gap.get("source_id")
    prefix = f"'{source}': " if source else ""
    return f"{prefix}{gap.get('detail', gap.get('rule', 'unknown'))}"


def _scope_statement(
    record: dict[str, Any], observation: dict[str, Any]
) -> str:
    """What this verdict covers — and expressly what it does not."""
    subject = _dict_field(record, "subject")
    repository = subject.get("repository") or "unknown repository"
    sha = str(subject.get("sha") or "")
    target = f"{repository}@{sha[:12]}" if sha else str(repository)
    inputs = record.get("inputs")
    required = sum(
        1
        for source in inputs
        if isinstance(source, dict) and source.get("required")
    ) if isinstance(inputs, list) else 0
    parts = [
        f"{required} required and policy-named advisory source(s) on "
        f"{target}"
    ]
    protection = observation.get("protection_source")
    if isinstance(protection, str) and protection not in ("", "none"):
        parts.append(f"requirements read from {protection}")
    if observation.get("strict_up_to_date_required"):
        parts.append(
            "GitHub additionally requires the branch to be up to date "
            "(not checked here)"
        )
    parts.append("not full merge-readiness")
    return "; ".join(parts)


def _freshness_statement(observation: dict[str, Any]) -> str:
    """When and how completely the world was observed."""
    observed_at = observation.get("observed_at")
    status = observation.get("status")
    if not isinstance(observed_at, str) or not observed_at:
        if isinstance(status, str) and status:
            return f"observation time not recorded; collection {status}"
        return "not recorded (offline or pre-freshness bundle)"
    text = f"observed {observed_at}"
    if isinstance(status, str) and status:
        text += f"; collection {status}"
    visibility = observation.get("workflow_visibility")
    if isinstance(visibility, dict):
        not_started = visibility.get("not_started")
        if isinstance(not_started, int) and not_started > 0:
            text += f"; {not_started} workflow unit(s) had not started"
    return text


def _effect_statement(record: dict[str, Any]) -> str:
    """What this verdict can actually do to the pipeline."""
    if record.get("can_block"):
        return "enforcing — a BLOCK verdict fails the calling job"
    return (
        "advisory — recorded evidence only; a BLOCK verdict does not "
        "fail the job"
    )


def render_markdown(record: Any) -> tuple[str, bool]:
    """Render a decision record as Markdown.

    Returns the Markdown text and whether the record's self-digest check
    passed. Raises :class:`InputError` when the value is not a decision
    record at all.
    """
    diag = diagnose(record)
    verdict = diag["verdict"]
    intact = diag["intact"]
    subject = diag["subject"]
    policy = diag["policy"]
    counts = diag["counts"]

    lines: list[str] = [f"## Gate decision: {verdict}", ""]
    summary = diag["summary"]
    if isinstance(summary, str) and summary:
        lines.append(f"**What happened:** {_escape(summary)}")
    lines.append(f"**Scope:** {_escape(diag['scope'])}")
    lines.append(f"**Freshness:** {_escape(diag['freshness'])}")
    lines.append(f"**Effect:** {_escape(diag['effect'])}")
    lines.append(
        "**Signals:** "
        f"{counts['required_total']} required "
        f"({counts['required_successful']} successful) · "
        f"{counts['advisory_total']} advisory "
        f"({counts['advisory_warnings']} warning(s))"
    )
    lines += [f"**Next:** {diag['next']}", ""]
    if not intact:
        lines += [
            "> **Warning:** record content does not match its self-digest. "
            "Do not trust this record.",
            "",
        ]

    # quiet PASS: an enforceably clean record needs no tables — the
    # digests line keeps it verifiable, and the full detail stays in the
    # record JSON and the HTML evidence view
    if (
        verdict == "PASS"
        and intact
        and not diag["reasons"]
        and counts["required_total"] > 0
    ):
        lines += [
            f"Record {_code(record.get('record_digest', '-'))} · "
            f"bundle {_code(record.get('input_bundle_digest', '-'))} · "
            "self-check OK · "
            f"{_escape(record.get('verification_status', '-'))}",
            "",
        ]
        return "\n".join(lines), intact

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
        "| Verification status | "
        f"{_escape(record.get('verification_status', '-'))} |"
    )
    lines.append("")

    if diag["dominant"] and diag["gaps_total"] > 1:
        lines += [
            f"**Dominant problem:** {_escape(diag['dominant'])}",
            "",
        ]
    if diag["gaps"]:
        lines += ["### Top gaps", ""]
        for reason in diag["gaps"]:
            severity = _escape(reason.get("severity", "-"))
            rule = reason.get("rule", "-")
            source = _escape(reason.get("source_id") or "-")
            detail = _escape(reason.get("detail", ""))
            lines.append(f"- {severity} {_code(rule)} {source}: {detail}")
            hint = REPAIR_HINTS.get(str(rule))
            if hint:
                lines.append(f"  - Hint: {hint}")
        remainder = diag["gaps_total"] - len(diag["gaps"])
        if remainder > 0:
            lines.append(
                f"- …and {remainder} more reason(s) — every one is in "
                "the record JSON and the HTML evidence view."
            )
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
        candidates = [
            source for source in sources
            if source.get("kind") == "github_check"
        ]
        candidate_ids = ", ".join(
            str(source.get("id", ""))
            .replace('"', "")
            .replace("`", "'")
            .replace("\n", " ")
            for source in candidates[:5]
        )
        if candidate_ids:
            lines.append(
                "- Suggestion: start with your detected checks, then trim: "
                f'`required-checks: "{candidate_ids}"`'
            )
    else:
        required_ids = ", ".join(
            _code(source.get("id", "-")) for source in required
        )
        lines.append(f"- Blocking on: {required_ids}")
    lines.append("")
    return lines


def _next_step(record: dict[str, Any], intact: bool) -> str:
    """One adaptive sentence telling the reader what to fix next."""
    if not intact:
        return (
            "do not act on this record; regenerate it from the source "
            "bundle and investigate the mutation"
        )
    verdict = record.get("verdict")
    reasons = record.get("reasons")
    if verdict == "BLOCK" and isinstance(reasons, list):
        # one concrete step: name the first blocking source
        for reason in reasons:
            if not isinstance(reason, dict):
                continue
            if reason.get("severity") != "BLOCK":
                continue
            rule = str(reason.get("rule"))
            source_id = reason.get("source_id")
            if rule == "missing_required_source" and source_id:
                return (
                    f"make the required check '{source_id}' report on "
                    "this exact commit (the name must match exactly), "
                    "or correct the required-checks name"
                )
            if rule == "failed_required_source" and source_id:
                return (
                    f"fix or re-run the required check '{source_id}', "
                    "then re-evaluate"
                )
            hint = REPAIR_HINTS.get(rule)
            if hint:
                return hint
    if verdict in ("BLOCK", "WARN") and isinstance(reasons, list):
        for reason in reasons:
            if isinstance(reason, dict):
                hint = REPAIR_HINTS.get(str(reason.get("rule")))
                if hint:
                    return hint
    inputs = record.get("inputs")
    sources = [s for s in inputs if isinstance(s, dict)] if isinstance(
        inputs, list
    ) else []
    if sources and not any(s.get("required") for s in sources):
        return (
            "define required checks so the gate can BLOCK "
            "(see the suggestion under Coverage)"
        )
    if not record.get("can_block"):
        return (
            'set enforce: "true" (or a blocking policy) so a BLOCK '
            "verdict fails the job"
        )
    return "nothing — the gate is enforcing and green"


_HTML_STYLE = (
    "body{font:15px/1.5 system-ui,sans-serif;max-width:46rem;"
    "margin:2rem auto;padding:0 1rem;color:#1a1a1a}"
    "table{border-collapse:collapse;width:100%;margin:.5rem 0}"
    "td,th{border:1px solid #ccc;padding:.3rem .6rem;text-align:left;"
    "font-size:.9rem}"
    "code{font:.85rem/1.4 ui-monospace,monospace;word-break:break-all}"
    ".verdict{display:inline-block;padding:.15rem .6rem;border-radius:6px;"
    "font-weight:700}"
    ".v-PASS{background:#d7f5dd}.v-WARN{background:#fdeec7}"
    ".v-BLOCK{background:#fbd7d7}"
    ".tampered{border:2px solid #b00;padding:.5rem .8rem;margin:.8rem 0;"
    "font-weight:600}"
    ".hint{color:#555;font-size:.85rem}"
    "footer{margin-top:1.5rem;color:#777;font-size:.8rem}"
)


def _h(value: Any) -> str:
    """HTML-escape an untrusted value rendered as text."""
    return _html.escape(
        str(value).replace("\r", " ").replace("\n", " "), quote=True
    )


def verify_bindings(
    record: dict[str, Any],
    *,
    bundle: Any = None,
    policy_path: Path | None = None,
) -> dict[str, str]:
    """Optional deep verification for evidence views.

    With the bundle and/or policy at hand, a view can state more than
    the record's self-digest: ``bundle_binding`` (the record was built
    from exactly this bundle), ``policy_binding`` (the shipped policy
    digests to the record's policy digest), and — with both —
    ``semantic_replay`` (re-evaluating the bundle against the policy
    reproduces the record's verdict, reasons, inputs, and subject; the
    generator version is excluded so records replay across releases).
    """
    results: dict[str, str] = {}
    if bundle is not None:
        bundle_subject = (
            bundle.get("subject") if isinstance(bundle, dict) else None
        )
        ok = (
            record.get("input_bundle_digest") == canonical.digest(bundle)
            and subject_identity(record.get("subject"))
            == subject_identity(bundle_subject)
        )
        results["bundle_binding"] = "OK" if ok else "FAILED"
    policy = None
    if policy_path is not None:
        try:
            policy = load_policy(policy_path)
        except InputError:
            results["policy_binding"] = "FAILED"
        else:
            recorded = record.get("policy")
            recorded_digest = (
                recorded.get("digest") if isinstance(recorded, dict) else None
            )
            results["policy_binding"] = (
                "OK" if policy.digest == recorded_digest else "FAILED"
            )
    if bundle is not None and policy is not None:
        decision = evaluate(bundle, policy)
        derived: dict[str, Any] = {
            "verdict": decision.verdict,
            "summary": decision.summary,
            "reasons": [reason.as_dict() for reason in decision.reasons],
            "inputs": decision.inputs,
            "subject": decision.subject.as_dict(),
        }
        ok = all(record.get(k) == v for k, v in derived.items())
        results["semantic_replay"] = "OK" if ok else "FAILED"
    return results


def render_html(
    record: Any, bindings: dict[str, str] | None = None
) -> tuple[str, bool]:
    """Render a decision record as a deterministic static HTML page.

    Built from the same :func:`diagnose` result as the Markdown summary,
    so the two views cannot drift in substance. The page is
    self-contained (inline CSS, no scripts, no external assets) and
    contains no timestamps — the same record always renders to the same
    bytes. This is a view over the existing record: no new command,
    contract, or semantics.
    """
    diag = diagnose(record)
    verdict = str(diag["verdict"])
    counts = diag["counts"]
    subject = diag["subject"]
    policy = diag["policy"]

    parts: list[str] = [
        "<!doctype html>",
        '<html lang="en"><head><meta charset="utf-8">',
        f"<title>Gate decision: {_h(verdict)}</title>",
        f"<style>{_HTML_STYLE}</style></head><body>",
        f'<h1>Gate decision: <span class="verdict v-{_h(verdict)}">'
        f"{_h(verdict)}</span></h1>",
    ]
    if not diag["intact"]:
        parts.append(
            '<p class="tampered">Record content does not match its '
            "self-digest. Do not trust this record.</p>"
        )
    summary = diag["summary"]
    if isinstance(summary, str) and summary:
        parts.append(f"<p><strong>What happened:</strong> {_h(summary)}</p>")
    parts.append(
        f"<p><strong>Scope:</strong> {_h(diag['scope'])}<br>"
        f"<strong>Freshness:</strong> {_h(diag['freshness'])}<br>"
        f"<strong>Effect:</strong> {_h(diag['effect'])}<br>"
        "<strong>Signals:</strong> "
        f"{counts['required_total']} required "
        f"({counts['required_successful']} successful) · "
        f"{counts['advisory_total']} advisory "
        f"({counts['advisory_warnings']} warning(s))<br>"
        f"<strong>Next:</strong> {_h(diag['next'])}</p>"
    )

    rows = [("Repository", subject.get("repository", "-"))]
    if subject.get("ref"):
        rows.append(("Ref", subject["ref"]))
    rows.append(("Commit", subject.get("sha", "-")))
    if subject.get("pull_request") is not None:
        rows.append(("Pull request", f"#{subject['pull_request']}"))
    rows += [
        ("Policy", f"{policy.get('policy_id', '-')} ({policy.get('mode', '-')})"),
        ("Policy digest", policy.get("digest", "-")),
        ("Input bundle digest", diag["input_bundle_digest"] or "-"),
        ("Record digest", diag["record_digest"] or "-"),
        ("Record self-check", "OK" if diag["intact"] else "FAILED"),
        ("Verification status", diag["verification_status"] or "-"),
    ]
    if bindings:
        labels = {
            "bundle_binding": "Bundle binding",
            "policy_binding": "Policy binding",
            "semantic_replay": "Semantic replay",
        }
        rows += [
            (labels[name], bindings[name])
            for name in ("bundle_binding", "policy_binding", "semantic_replay")
            if name in bindings
        ]
    parts.append("<table>")
    for label, value in rows:
        parts.append(
            f"<tr><th>{_h(label)}</th><td><code>{_h(value)}</code></td></tr>"
        )
    parts.append("</table>")

    if diag["reasons"]:
        parts.append("<h2>Reasons</h2><ul>")
        for reason in diag["reasons"]:
            line = (
                f"{_h(reason.get('severity', '-'))} "
                f"<code>{_h(reason.get('rule', '-'))}</code> "
                f"{_h(reason.get('source_id') or '-')}: "
                f"{_h(reason.get('detail', ''))}"
            )
            hint = REPAIR_HINTS.get(str(reason.get("rule")))
            if hint:
                line += f'<br><span class="hint">Hint: {_h(hint)}</span>'
            parts.append(f"<li>{line}</li>")
        parts.append("</ul>")

    if diag["inputs"]:
        parts.append(
            "<h2>Inputs</h2><table><tr><th>Id</th><th>Kind</th>"
            "<th>Required</th><th>Status</th></tr>"
        )
        for source in diag["inputs"]:
            parts.append(
                f"<tr><td>{_h(source.get('id', '-'))}</td>"
                f"<td>{_h(source.get('kind', '-'))}</td>"
                f"<td>{'yes' if source.get('required') else 'no'}</td>"
                f"<td>{_h(source.get('status', '-'))}</td></tr>"
            )
        parts.append("</table>")

    parts.append(
        "<footer>Generated by aos-workflow-gate from the decision record "
        "only; replay offline with <code>aos-workflow-gate verify</code>. "
        "Decision records carry UNSIGNED_NOT_OFFICIAL status; no "
        "production, compliance, or security-audit claim is made."
        "</footer></body></html>"
    )
    return "\n".join(parts) + "\n", diag["intact"]


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
