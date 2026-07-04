"""Decision record construction and verification.

The record preserves subject identity, policy identity and digest, the input
signal identities and digests, the verdict, and the explained reasons. It
carries a self-digest (``record_digest``) so that any later mutation of the
record is detectable, and an ``input_bundle_digest`` so a decision can be
replayed against its exact source bundle.
"""

from __future__ import annotations

from typing import Any

from . import canonical
from .evaluate import Decision
from .policy import Policy
from .version import __version__

SCHEMA_VERSION = "aos-workflow-gate-decision/v0"
RECORD_DIGEST_FIELD = "record_digest"


def build_record(
    decision: Decision, *, policy: Policy, input_bundle_digest: str
) -> dict[str, Any]:
    """Build the stable, self-verifying decision record."""
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generator": {"tool": "aos-workflow-gate", "version": __version__},
        "subject": decision.subject.as_dict(),
        "policy": {
            "policy_id": policy.policy_id,
            "mode": policy.mode,
            "verification_status": policy.verification_status,
            "digest": policy.digest,
        },
        "verdict": decision.verdict,
        "verification_status": policy.verification_status,
        "summary": decision.summary,
        "reasons": [reason.as_dict() for reason in decision.reasons],
        "inputs": decision.inputs,
        "input_bundle_digest": input_bundle_digest,
    }
    record[RECORD_DIGEST_FIELD] = canonical.digest(record)
    return record


def verify_record(record: Any) -> bool:
    """Return True if the record's self-digest matches its content."""
    if not isinstance(record, dict):
        return False
    claimed = record.get(RECORD_DIGEST_FIELD)
    if not isinstance(claimed, str):
        return False
    payload = {k: v for k, v in record.items() if k != RECORD_DIGEST_FIELD}
    return claimed == canonical.digest(payload)
