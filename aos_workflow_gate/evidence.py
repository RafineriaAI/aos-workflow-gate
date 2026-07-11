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
from .manifest import verifier_manifest_digest
from .policy import Policy
from .version import __version__

SCHEMA_VERSION = "aos-workflow-gate-decision/v0"
RECORD_DIGEST_FIELD = "record_digest"


def observation_from_bundle(bundle: Any) -> dict[str, Any] | None:
    """Compact projection of the bundle's collection provenance.

    The decision record must be self-describing for its reader: scope
    and freshness live in the bundle's ``collection``, so the record
    echoes the compact, display-relevant subset (never the raw API
    payloads). A bundle without a collection yields ``None`` — the
    record then honestly shows freshness as not recorded.
    """
    if not isinstance(bundle, dict):
        return None
    collection = bundle.get("collection")
    if not isinstance(collection, dict):
        return None
    observation: dict[str, Any] = {}
    for key in (
        "status",
        "observed_at",
        "github_baseline",
        "protection_source",
        "strict_up_to_date_required",
    ):
        if key in collection:
            observation[key] = collection[key]
    verifier = collection.get("verifier_change")
    if isinstance(verifier, dict):
        compact_verifier: dict[str, Any] = {
            "available": bool(verifier.get("analyzed"))
        }
        if verifier.get("analyzed"):
            compact_verifier.update(
                {
                    "non_independent_sources": len(
                        verifier.get("non_independent_sources") or []
                    ),
                    "routine_bump_excluded": bool(
                        verifier.get("routine_bump_excluded")
                    ),
                    "acknowledged": bool(verifier.get("acknowledged")),
                }
            )
        elif verifier.get("unavailable"):
            compact_verifier["unavailable"] = str(verifier["unavailable"])
        observation["verifier_change"] = compact_verifier
    visibility = collection.get("workflow_visibility")
    if isinstance(visibility, dict):
        compact: dict[str, Any] = {
            "available": bool(visibility.get("available"))
        }
        if isinstance(visibility.get("units_total"), int):
            compact["units_total"] = visibility["units_total"]
        not_started = visibility.get("not_started")
        if isinstance(not_started, list):
            compact["not_started"] = len(not_started)
            compact["action_required"] = sum(
                1
                for unit in not_started
                if isinstance(unit, dict)
                and unit.get("state") == "action_required"
            )
        observation["workflow_visibility"] = compact
    return observation or None


def build_record(
    decision: Decision,
    *,
    policy: Policy,
    input_bundle_digest: str,
    can_block: bool = False,
    observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the stable, self-verifying decision record.

    ``can_block`` records whether this evaluation, as configured, could
    have failed the calling process on a ``BLOCK`` verdict (blocking policy
    mode or explicit enforcement). A reader can then tell an enforcing gate
    from a purely advisory one without guessing. ``observation`` is the
    compact collection echo from :func:`observation_from_bundle`; it is
    part of the digested record, so scope and freshness statements are
    tamper-evident like everything else.
    """
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generator": {
            "tool": "aos-workflow-gate",
            "version": __version__,
            # content address of the exact verifier that derived this
            # decision: substitution becomes detectable, with no signing
            # or authorship claim (see docs, verifier manifest)
            "verifier_manifest_digest": verifier_manifest_digest(),
        },
        "subject": decision.subject.as_dict(),
        "policy": {
            "policy_id": policy.policy_id,
            "mode": policy.mode,
            "verification_status": policy.verification_status,
            "digest": policy.digest,
        },
        "verdict": decision.verdict,
        "can_block": can_block,
        "verification_status": policy.verification_status,
        "summary": decision.summary,
        "reasons": [reason.as_dict() for reason in decision.reasons],
        "inputs": decision.inputs,
        "input_bundle_digest": input_bundle_digest,
    }
    if observation is not None:
        record["observation"] = observation
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
