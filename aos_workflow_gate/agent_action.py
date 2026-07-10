"""Agent action adapter (``agent-action-v0``).

An *agent action document* describes what an agent intends to do or has
done: which repository, from which base commit, toward which subject,
with what declared intent, action type, and parameters. The adapter
validates the document and reduces it to a ``source-v0`` source whose
status is the validation state — evidence a policy can require, never
an approval.

Contract principles:

- **Agent-agnostic input.** Any agent harness can emit the document;
  the optional ``agent`` block is provenance data, not identity.
- **Validation–policy separation.** The adapter reports the validation
  state (``valid``, ``stale``, ``tampered``, ``subject_mismatch``,
  ``bounded_duplicate``); what any state means for the verdict is the
  policy's decision. A ``valid`` action maps to source status
  ``success`` — a fixed mechanical mapping like the SARIF one, so a
  policy can require a valid agent action. Success asserts structural
  integrity and binding only: **no semantic approval claim** is made and
  the adapter has **no execution authority** — it validates a
  description, it never runs anything.
- **Bounded duplicate detection.** Duplicates are detected within one
  invocation and against the target bundle — never globally. There is
  **no global duplicate or replay protection**; that boundary is stated
  in the source summary itself.

State precedence when several conditions hold: integrity first
(``tampered``), then binding (``subject_mismatch``), then freshness
failure (``stale``), then duplication (``bounded_duplicate``), then
unknown freshness (``freshness_unverified`` — no live or pinned base
was provided, so ``valid`` must not be claimed).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from . import canonical
from .collect import (
    DEFAULT_API_URL,
    Budget,
    _request_json,
    validate_api_url,
)
from .errors import InputError
from .source_contract import source_digest

AGENT_ACTION_CONTRACT = "agent-action-v0"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

VALID = "valid"
STALE = "stale"
TAMPERED = "tampered"
SUBJECT_MISMATCH = "subject_mismatch"
BOUNDED_DUPLICATE = "bounded_duplicate"
FRESHNESS_UNVERIFIED = "freshness_unverified"

DUPLICATE_SCOPE = "invocation+bundle"


def _require_str(doc: dict[str, Any], field: str, where: str) -> str:
    value = doc.get(field)
    if not isinstance(value, str) or not value:
        raise InputError(f"{where}.{field}: must be a non-empty string")
    return value


def _require_sha(doc: dict[str, Any], field: str, where: str) -> str:
    value = _require_str(doc, field, where)
    if not _SHA_RE.match(value):
        raise InputError(
            f"{where}.{field}: must be a 40-character lowercase hex "
            f"commit SHA, got {value!r}"
        )
    return value


def validate_action_document(doc: Any, *, where: str = "document") -> dict[str, Any]:
    """Structurally validate an ``agent-action-v0`` document.

    Errors are precise and path-addressed. This is operator/integrator
    tooling input, so a malformed document is a hard error (exit 2) —
    exactly like a malformed SARIF file. Validation *states* (stale,
    tampered, ...) are not errors: they are reported as the source
    status of a structurally sound document.
    """
    if not isinstance(doc, dict):
        raise InputError(f"{where}: must be a JSON object")
    contract = doc.get("contract")
    if contract != AGENT_ACTION_CONTRACT:
        raise InputError(
            f"{where}.contract: must be {AGENT_ACTION_CONTRACT!r}, "
            f"got {contract!r}"
        )
    _require_str(doc, "repository", where)
    _require_sha(doc, "base_sha", where)

    subject = doc.get("subject")
    if not isinstance(subject, dict):
        raise InputError(f"{where}.subject: must be a mapping")
    _require_str(subject, "repository", f"{where}.subject")
    _require_sha(subject, "sha", f"{where}.subject")
    if subject["repository"] != doc["repository"]:
        raise InputError(
            f"{where}.subject.repository: must equal the document's "
            "repository (cross-repository and fork flows are out of "
            "scope for agent-action-v0)"
        )

    intent = doc.get("intent")
    if not isinstance(intent, dict):
        raise InputError(f"{where}.intent: must be a mapping")
    _require_str(intent, "task", f"{where}.intent")

    action = doc.get("action")
    if not isinstance(action, dict):
        raise InputError(f"{where}.action: must be a mapping")
    _require_str(action, "type", f"{where}.action")
    parameters = action.get("parameters", {})
    if not isinstance(parameters, dict):
        raise InputError(f"{where}.action.parameters: must be a mapping")

    snapshot = doc.get("snapshot")
    if snapshot is not None and not isinstance(snapshot, dict):
        raise InputError(f"{where}.snapshot: must be a mapping if present")

    digests = doc.get("digests")
    if digests is not None:
        if not isinstance(digests, dict):
            raise InputError(f"{where}.digests: must be a mapping if present")
        for key, value in digests.items():
            if key not in ("intent", "action", "parameters", "snapshot"):
                raise InputError(
                    f"{where}.digests.{key}: unknown digest name (known: "
                    "intent, action, parameters, snapshot)"
                )
            if not isinstance(value, str) or not _DIGEST_RE.match(value):
                raise InputError(
                    f"{where}.digests.{key}: must match "
                    "sha256:<64 lowercase hex>"
                )

    agent = doc.get("agent")
    if agent is not None and not isinstance(agent, dict):
        raise InputError(f"{where}.agent: must be a mapping if present")
    return doc


def compute_digests(doc: dict[str, Any]) -> dict[str, str]:
    """Canonical digests binding intent, action, parameters, snapshot.

    ``action`` covers the full binding — type, parameters, intent,
    repository, base commit, and subject — so an identical action
    replayed against the same base state yields the same digest, which
    is exactly what bounded duplicate detection compares.
    """
    action = doc["action"]
    intent_digest = canonical.digest(doc["intent"])
    parameters_digest = canonical.digest(action.get("parameters", {}))
    digests = {
        "intent": intent_digest,
        "parameters": parameters_digest,
        "action": canonical.digest(
            {
                "type": action["type"],
                "intent_digest": intent_digest,
                "parameters_digest": parameters_digest,
                "repository": doc["repository"],
                "base_sha": doc["base_sha"],
                "subject": doc["subject"],
            }
        ),
    }
    if isinstance(doc.get("snapshot"), dict):
        digests["snapshot"] = canonical.digest(doc["snapshot"])
    return digests


def fetch_branch_head(
    repository: str,
    branch: str,
    *,
    token: str | None,
    api_url: str = DEFAULT_API_URL,
    budget: Budget | None = None,
) -> str:
    """Live-state lookup: the current head SHA of a branch."""
    api_url = validate_api_url(api_url)
    budget = budget or Budget()
    parts = repository.rstrip("/").rsplit("/", 2)
    slug = "/".join(parts[-2:]) if len(parts) >= 2 else repository
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = _request_json(
        f"{api_url}/repos/{slug}/branches/{branch}",
        headers,
        timeout=30.0,
        budget=budget,
    )
    if not isinstance(payload, dict):
        raise InputError("branch API response is not a JSON object")
    commit = payload.get("commit") or {}
    sha = commit.get("sha")
    if not isinstance(sha, str) or not sha:
        raise InputError(f"branch {branch!r} has no resolvable head commit")
    return sha


def classify_action(
    doc: dict[str, Any],
    *,
    bundle_subject: dict[str, Any] | None = None,
    observed_base: str | None = None,
    validation_mode: str = "none",
    seen_action_digests: set[str] | None = None,
    duplicate_of: str | None = None,
) -> tuple[str, str]:
    """Classify a validated document into (state, explanation).

    Precedence: tampered, then subject_mismatch, then stale, then
    bounded_duplicate, then freshness_unverified, then valid.
    ``observed_base`` is the head SHA the base is compared against
    (live branch head or pinned value); when it is absent the document
    cannot reach ``valid`` — unknown freshness is stated, not assumed.
    """
    computed = compute_digests(doc)
    claimed = doc.get("digests")
    if isinstance(claimed, dict):
        for name, value in claimed.items():
            if computed.get(name) != value:
                return TAMPERED, (
                    f"Agent action tampered: claimed {name} digest does "
                    "not match the recomputed canonical digest."
                )

    subject = doc["subject"]
    if bundle_subject is not None:
        for key in ("repository", "sha"):
            expected = bundle_subject.get(key)
            if expected is not None and subject.get(key) != expected:
                return SUBJECT_MISMATCH, (
                    f"Agent action subject mismatch: document subject "
                    f"{key} {subject.get(key)!r} does not match bundle "
                    f"subject {key} {expected!r}."
                )

    if observed_base is not None and doc["base_sha"] != observed_base:
        return STALE, (
            f"Agent action stale: base {doc['base_sha'][:12]} is not "
            f"the observed head {observed_base[:12]} "
            f"({validation_mode} check); the action was prepared "
            "against a state that has moved."
        )

    if seen_action_digests is not None:
        if computed["action"] in seen_action_digests:
            first = f" of '{duplicate_of}'" if duplicate_of else ""
            return BOUNDED_DUPLICATE, (
                "Agent action bounded duplicate: same action digest"
                f"{first} within this bundle/invocation (bounded scope; "
                "no global duplicate or replay protection exists)."
            )

    if observed_base is None:
        return FRESHNESS_UNVERIFIED, (
            "Agent action freshness unverified: no live or pinned base "
            "was provided, so staleness against the base state was not "
            "evaluated. This fails closed for required sources; pass "
            "--live or --pinned-base to verify freshness."
        )
    return VALID, (
        f"Agent action valid: structurally intact, bound to "
        f"{doc['repository']}@{doc['base_sha'][:12]}, "
        f"{validation_mode} staleness check passed. "
        "Validity is structural and binding only — no semantic "
        "approval of the change is implied."
    )


def action_source(
    doc: dict[str, Any],
    state: str,
    explanation: str,
    *,
    validation_mode: str,
    source_id: str | None = None,
) -> dict[str, Any]:
    """Reduce a classified document to a ``source-v0`` source.

    ``valid`` maps to status ``success`` (fixed mechanical mapping, so a
    policy can require a valid agent action); every other state is the
    status verbatim, failing closed for required sources and warning for
    advisory ones.
    """
    computed = compute_digests(doc)
    identity = {
        "action_digest": computed["action"],
        "intent_digest": computed["intent"],
        "parameters_digest": computed["parameters"],
        "snapshot_digest": computed.get("snapshot"),
        "repository": doc["repository"],
        "base_sha": doc["base_sha"],
        "subject": doc["subject"],
        "validation_mode": validation_mode,
        "duplicate_scope": DUPLICATE_SCOPE,
        "status": "success" if state == VALID else state,
    }
    return {
        "id": source_id or f"agent.action.{computed['action'][7:19]}",
        "kind": "agent_action",
        "signal_source": "agent_action_adapter",
        "status": identity["status"],
        "summary": explanation,
        "identity": identity,
        "digest": source_digest(identity),
        "contract": "source-v0",
    }


def load_action_document(path: Path) -> dict[str, Any]:
    """Load and structurally validate one action document file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"cannot read action document {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON: {exc}") from exc
    return validate_action_document(payload, where=str(path))
