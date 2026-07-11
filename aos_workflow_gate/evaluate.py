"""Core gate evaluation.

Given an untrusted signal bundle and a validated policy, produce a
``Decision`` whose ``verdict`` is one of ``PASS``, ``WARN``, or ``BLOCK`` and
whose ``reasons`` explain exactly why. Untrusted input fails closed: a
structurally malformed bundle yields a ``BLOCK`` decision with a
``malformed_input`` reason rather than an exception, so there is always a
replayable record of *why* the gate refused.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import InputError
from .policy import Policy
from .source_contract import (
    SOURCE_CONTRACT_VERSION,
    contract_violation,
    validate_source_v0,
)

PASS = "PASS"
WARN = "WARN"
BLOCK = "BLOCK"

_PRECEDENCE = {PASS: 0, WARN: 1, BLOCK: 2}
_SUCCESS = "success"


@dataclass(frozen=True)
class Reason:
    """One explained contribution to a verdict."""

    rule: str
    severity: str
    source_id: str | None
    detail: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "source_id": self.source_id,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class Subject:
    repository: str | None
    ref: str | None
    sha: str | None
    pull_request: int | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "repository": self.repository,
            "ref": self.ref,
            "sha": self.sha,
            "pull_request": self.pull_request,
        }


@dataclass(frozen=True)
class Source:
    id: str
    kind: str
    status: str
    required: bool
    digest: str | None
    summary: str | None
    signal_source: str | None = None

    def as_input(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "status": self.status,
            "required": self.required,
            "digest": self.digest,
            "signal_source": self.signal_source,
        }


@dataclass
class Decision:
    """The evaluated gate decision and its explanation."""

    subject: Subject
    verdict: str
    summary: str
    reasons: list[Reason] = field(default_factory=list)
    inputs: list[dict[str, Any]] = field(default_factory=list)


def combine(severities: list[str]) -> str:
    """Return the highest-precedence verdict; ``PASS`` if empty."""
    verdict = PASS
    for severity in severities:
        if _PRECEDENCE.get(severity, 0) > _PRECEDENCE[verdict]:
            verdict = severity
    return verdict


def evaluate(bundle: Any, policy: Policy) -> Decision:
    """Evaluate an untrusted signal bundle against a policy."""
    malformed: list[Reason] = []
    malformed_severity = policy.rules["malformed_input"]

    if not isinstance(bundle, dict):
        malformed.append(
            Reason(
                "malformed_input",
                malformed_severity,
                None,
                "signal bundle must be a JSON object",
            )
        )
        return _build(Subject(None, None, None, None), policy, malformed, [])

    subject = _normalize_subject(bundle, policy, malformed)
    sources = _normalize_sources(
        bundle, malformed_severity, malformed,
        required_ids=frozenset(policy.required_sources),
    )

    if malformed or sources is None:
        inputs = [s.as_input() for s in sources] if sources else []
        return _build(subject, policy, malformed, inputs)

    requirement_states: dict[str, str] = {}
    collection = bundle.get("collection")
    if isinstance(collection, dict):
        for entry in collection.get("requirements") or []:
            if isinstance(entry, dict) and isinstance(
                entry.get("context"), str
            ):
                requirement_states[entry["context"]] = str(
                    entry.get("state", "")
                )

    reasons = _apply_rules(sources, policy, requirement_states)
    reasons.extend(_collection_reasons(collection, policy))
    inputs = [s.as_input() for s in sorted(sources, key=lambda s: s.id)]
    return _build(subject, policy, reasons, inputs)


def _collection_reasons(collection: Any, policy: Policy) -> list[Reason]:
    """A verdict must not read cleaner than its collection.

    When the bundle records how it was collected and that collection did
    not end ``complete`` (truncated listing, wait timeout, or any state
    this version does not know), the decision carries an
    ``incomplete_collection`` reason — WARN by default, policy-tunable —
    so an incomplete or unknown observation can never yield a plain
    PASS. Bundles that record no collection at all make no completeness
    claim and are unaffected.
    """
    if not isinstance(collection, dict) or "status" not in collection:
        return []
    status = str(collection.get("status"))
    if status == "complete":
        return []
    return [
        Reason(
            "incomplete_collection",
            policy.rules.get("incomplete_collection", "WARN"),
            None,
            f"collection ended '{status}', not 'complete': signals that "
            "exist for this commit may be absent from the bundle, so a "
            "clean result cannot be read as a complete PASS",
        )
    ]


def _apply_rules(
    sources: list[Source],
    policy: Policy,
    requirement_states: dict[str, str] | None = None,
) -> list[Reason]:
    reasons: list[Reason] = []
    index = {source.id: source for source in sources}
    states = requirement_states or {}

    if not policy.required_sources:
        reasons.append(
            Reason(
                "no_required_sources",
                policy.rules.get("no_required_sources", "WARN"),
                None,
                "the policy requires nothing, so no missing or failed "
                "check can make this gate BLOCK — the record is "
                "evidence, not enforcement",
            )
        )

    for required_id in policy.required_sources:
        source = index.get(required_id)
        if source is None:
            state = states.get(required_id)
            detail = "required source is absent from the bundle"
            if state in ("pending", "unverifiable", "missing"):
                detail += f" (requirement state: {state})"
            reasons.append(
                Reason(
                    "missing_required_source",
                    policy.rules["missing_required_source"],
                    required_id,
                    detail,
                )
            )
        elif source.status.lower() != _SUCCESS:
            reasons.append(
                Reason(
                    "failed_required_source",
                    policy.rules["failed_required_source"],
                    required_id,
                    f"required source status is '{source.status}'",
                )
            )

    for advisory_id in policy.advisory_sources:
        source = index.get(advisory_id)
        if source is not None and source.status.lower() != _SUCCESS:
            reasons.append(
                Reason(
                    "advisory_warning",
                    policy.rules["advisory_warning"],
                    advisory_id,
                    f"advisory source status is '{source.status}'",
                )
            )
    return reasons


def _normalize_subject(
    bundle: dict[str, Any], policy: Policy, malformed: list[Reason]
) -> Subject:
    raw = bundle.get("subject", {})
    if not isinstance(raw, dict):
        malformed.append(
            Reason(
                "malformed_input",
                policy.rules["malformed_input"],
                None,
                "subject must be a mapping",
            )
        )
        raw = {}

    repository = raw.get("repository")
    ref = raw.get("ref")
    sha = raw.get("sha")
    pull_request = raw.get("pull_request")

    if policy.require_repository and not _is_nonempty_str(repository):
        malformed.append(
            Reason(
                "malformed_input",
                policy.rules["malformed_input"],
                None,
                "policy requires subject.repository",
            )
        )
    if policy.require_sha and not _is_nonempty_str(sha):
        malformed.append(
            Reason(
                "malformed_input",
                policy.rules["malformed_input"],
                None,
                "policy requires subject.sha",
            )
        )

    return Subject(
        repository=repository if isinstance(repository, str) else None,
        ref=ref if isinstance(ref, str) else None,
        sha=sha if isinstance(sha, str) else None,
        pull_request=pull_request if isinstance(pull_request, int) else None,
    )


def _normalize_sources(
    bundle: dict[str, Any],
    malformed_severity: str,
    malformed: list[Reason],
    *,
    required_ids: frozenset[str],
) -> list[Source] | None:
    raw_sources = bundle.get("sources")
    if not isinstance(raw_sources, list):
        malformed.append(
            Reason(
                "malformed_input", malformed_severity, None, "sources must be a list"
            )
        )
        return None

    sources: list[Source] = []
    seen: set[str] = set()
    for position, item in enumerate(raw_sources):
        source = _normalize_source(
            item, position, malformed_severity, malformed, seen, required_ids
        )
        if source is None:
            return None
        sources.append(source)
    return sources


def _normalize_source(
    item: Any,
    position: int,
    malformed_severity: str,
    malformed: list[Reason],
    seen: set[str],
    required_ids: frozenset[str],
) -> Source | None:
    def reject(detail: str) -> None:
        malformed.append(Reason("malformed_input", malformed_severity, None, detail))

    if not isinstance(item, dict):
        reject(f"source at position {position} must be an object")
        return None
    is_source_v0 = item.get("contract") == SOURCE_CONTRACT_VERSION
    if is_source_v0:
        try:
            item = validate_source_v0(
                item, where=f"sources[{position}]"
            )
        except InputError as exc:
            reject(str(exc))
            return None
    source_id = item.get("id")
    if not _is_nonempty_str(source_id):
        reject(f"source at position {position} is missing a string id")
        return None
    assert isinstance(source_id, str)
    if source_id in seen:
        reject(f"duplicate source id '{source_id}'")
        return None
    kind = item.get("kind")
    if not _is_nonempty_str(kind):
        reject(f"source '{source_id}' is missing a string kind")
        return None
    status = item.get("status")
    if not _is_nonempty_str(status):
        reject(f"source '{source_id}' is missing a string status")
        return None
    if not is_source_v0:
        # Legacy draft-0 sources retain compatibility validation. Explicit
        # source-v0 inputs have already passed the complete import validator.
        violation = contract_violation(item)
        if violation is not None:
            reject(f"source '{source_id}' {violation}")
            return None
    # required/advisory classification is policy-owned: the record's
    # required flag is derived from the policy, never trusted from the
    # bundle. A legacy draft-0 'required' display field is still
    # type-checked, then ignored.
    legacy_required = item.get("required", False)
    if not isinstance(legacy_required, bool):
        reject(f"source '{source_id}' field 'required' must be a boolean")
        return None
    required = source_id in required_ids
    digest = item.get("digest")
    if digest is not None and not isinstance(digest, str):
        reject(f"source '{source_id}' field 'digest' must be a string")
        return None
    summary = item.get("summary")
    if summary is not None and not isinstance(summary, str):
        reject(f"source '{source_id}' field 'summary' must be a string")
        return None
    signal_source = item.get("signal_source")
    if signal_source is not None and not isinstance(signal_source, str):
        reject(f"source '{source_id}' field 'signal_source' must be a string")
        return None

    seen.add(source_id)
    assert isinstance(kind, str)
    assert isinstance(status, str)
    return Source(
        source_id, kind, status, required, digest, summary, signal_source
    )


def _build(
    subject: Subject,
    policy: Policy,
    reasons: list[Reason],
    inputs: list[dict[str, Any]],
) -> Decision:
    ordered = sorted(reasons, key=lambda r: (r.source_id or "", r.rule))
    verdict = combine([r.severity for r in ordered])
    summary = _summary(verdict, ordered)
    return Decision(
        subject=subject,
        verdict=verdict,
        summary=summary,
        reasons=ordered,
        inputs=inputs,
    )


def _summary(verdict: str, reasons: list[Reason]) -> str:
    if verdict == BLOCK:
        blocking = [r for r in reasons if r.severity == BLOCK]
        detail = "; ".join(f"{r.rule}:{r.source_id or '-'}" for r in blocking)
        return f"Gate BLOCK: {len(blocking)} blocking issue(s). {detail}".strip()
    if verdict == WARN:
        warnings = [r for r in reasons if r.severity == WARN]
        if any(r.rule == "no_required_sources" for r in warnings):
            return (
                f"Gate WARN: the policy requires nothing, so nothing "
                f"can block; {len(warnings)} warning(s)."
            )
        return (
            f"Gate WARN: required checks satisfied; "
            f"{len(warnings)} advisory warning(s)."
        )
    return "Gate PASS: all required checks satisfied; no advisory warnings."


def _is_nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)
