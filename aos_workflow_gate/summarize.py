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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import canonical
from .errors import InputError
from .evaluate import evaluate
from .evidence import subject_identity, verify_record
from .policy import load_policy

VERDICTS = ("PASS", "WARN", "BLOCK")

@dataclass(frozen=True)
class RemediationSpec:
    """Stable machine code plus the deterministic operator action."""

    code: str
    action: str


GENERIC_REMEDIATIONS: dict[str, RemediationSpec] = {
    "missing_required_source": RemediationSpec(
        "required_source_unclassified",
        "no completed check run with this exact name was found on the "
        "commit; verify the name or wait for the check to finish, then "
        "re-run the gate",
    ),
    "failed_required_source": RemediationSpec(
        "required_source_non_success",
        "the required check did not conclude success; fix or re-run it, "
        "then re-evaluate",
    ),
    "advisory_warning": RemediationSpec(
        "review_advisory_source",
        "advisory findings warn but never block; review the source's own "
        "report and decide",
    ),
    "no_required_sources": RemediationSpec(
        "define_required_sources",
        "nothing is required, so nothing can block; name required "
        "checks (see the suggestion under Coverage) to close the "
        "decision gap",
    ),
    "malformed_input": RemediationSpec(
        "repair_signal_bundle",
        "the signal bundle does not match schema draft-0; compare with "
        "examples/github-pr-signal-bundle.json",
    ),
    "incomplete_collection": RemediationSpec(
        "recollect_evidence",
        "the collection did not observe everything that may exist for "
        "this commit; re-collect with a larger wait/API budget, or "
        "accept the record as evidence of a bounded observation",
    ),
    "non_independent_evidence": RemediationSpec(
        "require_independent_evidence",
        "the named checks were produced by a workflow this change "
        "modifies; require evidence from a verifier governed outside "
        "the change",
    ),
    "verifier_change_unavailable": RemediationSpec(
        "restore_verifier_change_analysis",
        "the verifier-change analysis was incomplete; grant the named "
        "read permission, remove the collection error, and re-run",
    ),
}

# Compatibility view for integrations that only need one hint per rule.
REPAIR_HINTS = {
    rule: remediation.action
    for rule, remediation in GENERIC_REMEDIATIONS.items()
}

STATE_REMEDIATIONS: dict[tuple[str, str], RemediationSpec] = {
    ("missing_required_source", "missing"): RemediationSpec(
        "required_source_missing",
        "restore the workflow that emits '{source}' or remove the "
        "obsolete required-check setting, then re-run the gate",
    ),
    ("missing_required_source", "pending"): RemediationSpec(
        "required_source_pending",
        "wait for required check '{source}' to finish or increase the "
        "wait budget, then re-run the gate",
    ),
    ("missing_required_source", "unverifiable"): RemediationSpec(
        "required_source_unverifiable",
        "restore app identity or API visibility for required check "
        "'{source}' on this exact commit, then re-run the gate",
    ),
    ("failed_required_source", "failure"): RemediationSpec(
        "required_source_failed",
        "fix or re-run the required check '{source}', then re-evaluate",
    ),
    ("failed_required_source", "cancelled"): RemediationSpec(
        "required_source_cancelled",
        "re-run cancelled required check '{source}' and remove the "
        "cancellation cause before re-evaluating",
    ),
    ("failed_required_source", "timed_out"): RemediationSpec(
        "required_source_timed_out",
        "fix the timeout for required check '{source}', then re-run it "
        "and re-evaluate",
    ),
    ("failed_required_source", "skipped"): RemediationSpec(
        "required_source_skipped",
        "make required check '{source}' execute for this change instead "
        "of skipping, then re-evaluate",
    ),
    ("failed_required_source", "neutral"): RemediationSpec(
        "required_source_neutral",
        "make required check '{source}' report explicit success for the "
        "required evidence, then re-evaluate",
    ),
    ("failed_required_source", "action_required"): RemediationSpec(
        "required_source_action_required",
        "approve or authorize required check '{source}', then let it "
        "finish and re-evaluate",
    ),
    ("failed_required_source", "stale"): RemediationSpec(
        "required_source_stale",
        "revalidate or regenerate stale required evidence '{source}' "
        "against the current base, then re-evaluate",
    ),
    ("failed_required_source", "startup_failure"): RemediationSpec(
        "required_source_startup_failure",
        "repair the workflow startup failure for required check "
        "'{source}', then re-run and re-evaluate",
    ),
    ("failed_required_source", "tampered"): RemediationSpec(
        "required_source_tampered",
        "discard tampered required evidence '{source}' and regenerate "
        "it from the original action before re-evaluating",
    ),
    ("failed_required_source", "subject_mismatch"): RemediationSpec(
        "required_source_subject_mismatch",
        "collect required evidence '{source}' bound to this exact "
        "repository and head SHA, then re-evaluate",
    ),
    ("failed_required_source", "bounded_duplicate"): RemediationSpec(
        "required_source_bounded_duplicate",
        "provide a distinct required action for '{source}' or remove "
        "the duplicate from this bundle, then re-evaluate",
    ),
    ("failed_required_source", "freshness_unverified"): RemediationSpec(
        "required_source_freshness_unverified",
        "validate required evidence '{source}' against a live or pinned "
        "base state, then re-evaluate",
    ),
    ("incomplete_collection", "wait_timeout"): RemediationSpec(
        "collection_wait_timeout",
        "increase the wait budget or wait for checks to settle, then "
        "collect this exact commit again",
    ),
    ("incomplete_collection", "subject_mismatch"): RemediationSpec(
        "collection_subject_mismatch",
        "discard cross-subject observations and collect repository and "
        "head SHA evidence for this exact subject again",
    ),
    ("incomplete_collection", "truncated"): RemediationSpec(
        "collection_truncated",
        "increase the API page budget until collection is complete, "
        "then collect this exact commit again",
    ),
}


def diagnose(record: Any) -> dict[str, Any]:
    """Build the single structural diagnosis used by every renderer.

    Display text is never interpreted. Operational meaning comes from
    reason rule/state, input status, and observation status. Historical
    records without state receive the rule-level fallback.
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
    observation = _dict_field(record, "observation")

    missing_reasons = [
        reason for reason in reasons
        if reason.get("rule") == "missing_required_source"
    ]
    missing_states = [
        state
        if (state := _reason_state(reason, inputs, observation))
        in {"missing", "pending", "unverifiable"}
        else "missing"
        for reason in missing_reasons
    ]
    required_total = _required_source_count(required, missing_reasons)
    counts = {
        "required_total": required_total,
        "required_successful": sum(
            1 for source in required
            if str(source.get("status", "")).lower() == "success"
        ),
        "required_failed": sum(
            1 for reason in reasons
            if reason.get("rule") == "failed_required_source"
        ),
        "required_missing": missing_states.count("missing"),
        "required_pending": missing_states.count("pending"),
        "required_unverifiable": missing_states.count("unverifiable"),
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
    ranked = _rank_gaps(reasons)
    reason_views = [
        _reason_view(reason, inputs, observation) for reason in reasons
    ]
    gap_views = [
        _reason_view(reason, inputs, observation) for reason in ranked
    ]
    if not intact:
        remediation = _remediation(
            "record_integrity_failed",
            "do not act on this record; regenerate it from the source "
            "bundle and investigate the mutation",
        )
    elif gap_views:
        remediation = gap_views[0]["remediation"]
    else:
        remediation = _fallback_remediation(record, inputs)

    return {
        "verdict": verdict,
        "intact": intact,
        "summary": record.get("summary"),
        "can_block": bool(record.get("can_block")),
        "counts": counts,
        "next": remediation["action"],
        "remediation": remediation,
        "scope": _scope_statement(record, observation, required_total),
        "freshness": _freshness_statement(observation),
        "effect": _effect_statement(record),
        "gaps": gap_views[:3],
        "gaps_total": len(gap_views),
        "dominant": _dominant_problem(ranked),
        "observation": observation,
        "subject": _dict_field(record, "subject"),
        "policy": _dict_field(record, "policy"),
        "reasons": reason_views,
        "inputs": inputs,
        "record_digest": record.get("record_digest"),
        "input_bundle_digest": record.get("input_bundle_digest"),
        "verification_status": record.get("verification_status"),
    }


def _required_source_count(
    required: list[dict[str, Any]],
    missing_reasons: list[dict[str, Any]],
) -> int:
    """Count required identities, including controls absent from inputs."""
    source_ids = {
        str(source["id"])
        for source in required
        if source.get("id") is not None
    }
    anonymous = 0
    for reason in missing_reasons:
        source_id = reason.get("source_id")
        if source_id is None:
            anonymous += 1
        else:
            source_ids.add(str(source_id))
    return len(source_ids) + anonymous


def _reason_state(
    reason: dict[str, Any],
    inputs: list[dict[str, Any]],
    observation: dict[str, Any],
) -> str | None:
    """Resolve operational state from structured fields only."""
    explicit = reason.get("state")
    if isinstance(explicit, str) and explicit:
        return explicit.lower()

    rule = reason.get("rule")
    if rule in {"failed_required_source", "advisory_warning"}:
        source_id = reason.get("source_id")
        for source in inputs:
            if source.get("id") == source_id:
                status = source.get("status")
                if isinstance(status, str) and status:
                    return status.lower()
                break
    if rule == "incomplete_collection":
        status = observation.get("status")
        if isinstance(status, str) and status:
            return status.lower()
    return None


def _reason_view(
    reason: dict[str, Any],
    inputs: list[dict[str, Any]],
    observation: dict[str, Any],
) -> dict[str, Any]:
    return {
        **reason,
        "remediation": _remediation_for_reason(
            reason, inputs, observation
        ),
    }


def _remediation_for_reason(
    reason: dict[str, Any],
    inputs: list[dict[str, Any]],
    observation: dict[str, Any],
) -> dict[str, Any]:
    rule = str(reason.get("rule") or "")
    state = _reason_state(reason, inputs, observation)
    spec = STATE_REMEDIATIONS.get((rule, state or ""))
    if spec is None:
        spec = GENERIC_REMEDIATIONS.get(rule)
    if spec is None:
        spec = RemediationSpec(
            "review_unknown_reason",
            "review the complete reason in the decision record and "
            "resolve its named source before re-running the gate",
        )

    source_id = reason.get("source_id")
    source = (
        str(source_id).replace("\r", " ").replace("\n", " ")
        if source_id is not None
        else "the required check"
    )
    return _remediation(
        spec.code,
        spec.action.format(source=source),
        rule=rule or None,
        state=state,
        source_id=source_id,
    )


def _fallback_remediation(
    record: dict[str, Any], inputs: list[dict[str, Any]]
) -> dict[str, Any]:
    if record.get("verdict") != "PASS":
        return _remediation(
            "review_unexplained_verdict",
            "review the complete decision record because the non-PASS "
            "verdict contains no structured reason",
        )
    if inputs and not any(source.get("required") for source in inputs):
        return _remediation(
            "define_required_sources",
            "define required checks so the gate can BLOCK "
            "(see the suggestion under Coverage)",
        )
    if not record.get("can_block"):
        return _remediation(
            "enable_enforcement",
            'set enforce: "true" (or a blocking policy) so a BLOCK '
            "verdict fails the job",
        )
    return _remediation(
        "no_action",
        "nothing - the gate is enforcing and green",
    )


def _remediation(
    code: str,
    action: str,
    *,
    rule: str | None = None,
    state: str | None = None,
    source_id: Any = None,
) -> dict[str, Any]:
    value: dict[str, Any] = {"code": code, "action": action}
    if rule is not None:
        value["rule"] = rule
    if state is not None:
        value["state"] = state
    if source_id is not None:
        value["source_id"] = source_id
    return value


_GAP_RULE_RANK = {
    "malformed_input": 0,
    "missing_required_source": 1,
    "failed_required_source": 1,
    "verifier_change_unavailable": 2,
    "non_independent_evidence": 2,
    "incomplete_collection": 3,
    "no_required_sources": 4,
    "advisory_warning": 5,
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
    record: dict[str, Any],
    observation: dict[str, Any],
    required_total: int,
) -> str:
    """What this verdict covers — and expressly what it does not."""
    subject = _dict_field(record, "subject")
    repository = subject.get("repository") or "unknown repository"
    sha = str(subject.get("sha") or "")
    target = f"{repository}@{sha[:12]}" if sha else str(repository)
    parts = [
        f"{required_total} required and policy-named advisory source(s) on "
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
    lines += [f"**Next:** {_escape(diag['next'])}", ""]
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
            remediation = reason.get("remediation")
            if isinstance(remediation, dict):
                action = remediation.get("action")
                if isinstance(action, str) and action:
                    lines.append(f"  - Hint: {_escape(action)}")
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
            remediation = reason.get("remediation")
            if isinstance(remediation, dict):
                action = remediation.get("action")
                if isinstance(action, str) and action:
                    line += f'<br><span class="hint">Hint: {_h(action)}</span>'
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
