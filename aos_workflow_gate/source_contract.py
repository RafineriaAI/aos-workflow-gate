"""The versioned external source contract (``source-v0``).

A *source* is one observed signal inside a bundle. ``source-v0`` is the
first versioned contract for sources produced **outside** this package —
third-party adapters, scripts, and agent tooling emit plain JSON that
validates here; the gate never loads third-party code (no plugin
runtime).

Contract principles:

- **Adapter-defined, non-enum status.** ``status`` is any non-empty
  string chosen by the adapter. Exactly ``success`` passes downstream;
  every other value is preserved verbatim and interpreted by the policy.
  The status is an observation, never a verdict.
- **Identity-only digest.** ``digest`` is ``sha256:`` over the canonical
  JSON of the adapter's identity object — nothing else. The
  **identity-completeness invariant** requires the identity to contain
  the ``status`` and every decision-relevant observation, so two sources
  with equal digests cannot justify different decisions. The
  :func:`source_digest` helper enforces the invariant mechanically.
- **Policy-owned classification.** The contract has **no** ``required``
  field: whether a source is required or advisory is the policy's
  decision, recorded in the policy and derived at evaluation time. A
  signal must not be able to promote itself.

Legacy ``draft-0`` bundle sources (which may carry a ``required``
display field) remain accepted indefinitely; their ``required`` value is
ignored for classification. Committed historical records are never
rewritten.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from . import canonical
from .errors import InputError

SOURCE_CONTRACT_VERSION = "source-v0"

_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

_REQUIRED_FIELDS = ("id", "kind", "status", "digest")
_OPTIONAL_STR_FIELDS = ("summary", "signal_source", "observed_at")
_KNOWN_FIELDS = frozenset(
    _REQUIRED_FIELDS + _OPTIONAL_STR_FIELDS + ("contract", "identity")
)


_NO_EXPECTED_STATUS = object()


def _identity_value_violation(
    value: Any, *, where: str = "identity"
) -> str | None:
    """Return why an identity value is outside the deterministic JSON domain."""
    if isinstance(value, float):
        return (
            f"{where}: floats are not allowed in source identity; "
            "encode exact numeric values as strings"
        )
    if value is None or isinstance(value, (str, bool, int)):
        return None
    if isinstance(value, list):
        for position, item in enumerate(value):
            violation = _identity_value_violation(
                item, where=f"{where}[{position}]"
            )
            if violation is not None:
                return violation
        return None
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            return f"{where}: object keys must be strings"
        for key in sorted(value):
            violation = _identity_value_violation(
                value[key], where=f"{where}.{key}"
            )
            if violation is not None:
                return violation
        return None
    return f"{where}: unsupported JSON value type {type(value).__name__!r}"


def _identity_violation(
    identity: Any, *, expected_status: Any = _NO_EXPECTED_STATUS
) -> str | None:
    if not isinstance(identity, dict):
        return "identity must be a mapping"
    if "status" not in identity:
        return "identity omits 'status' (identity-completeness invariant)"
    if (
        expected_status is not _NO_EXPECTED_STATUS
        and identity.get("status") != expected_status
    ):
        return (
            f"status {expected_status!r} does not match the "
            f"identity's status {identity.get('status')!r}"
        )
    return _identity_value_violation(identity)


def source_digest(identity: dict[str, Any]) -> str:
    """Digest an adapter identity object under the completeness invariant.

    The identity must be a mapping that contains a ``status`` key — the
    mechanical half of the identity-completeness invariant. The other
    half (include every decision-relevant observation) is the adapter
    author's obligation, stated in docs/SOURCE_CONTRACT.md.
    """
    violation = _identity_violation(identity)
    if violation is not None:
        raise InputError(f"source {violation}")
    return canonical.digest(identity)


def contract_violation(item: dict[str, Any]) -> str | None:
    """Return the contract-level violation in a source, if any.

    This helper preserves contract-version and identity-binding checks for
    legacy bundle sources. Explicit source-v0 inputs use the complete
    validate_source_v0 path in both import and evaluate.
    """
    contract = item.get("contract")
    if contract is not None and contract != SOURCE_CONTRACT_VERSION:
        return f"declares unknown contract {contract!r}"
    if contract == SOURCE_CONTRACT_VERSION and "required" in item:
        return (
            "carries a 'required' field, but the source-v0 contract has "
            "none: required/advisory classification is policy-owned"
        )
    identity = item.get("identity")
    if identity is not None:
        violation = _identity_violation(
            identity, expected_status=item.get("status")
        )
        if violation is not None:
            return violation
        declared = item.get("digest")
        if isinstance(declared, str) and declared:
            recomputed = canonical.digest(identity)
            if recomputed != declared:
                return (
                    "digest does not recompute from the attached "
                    "identity (identity binding violated)"
                )
    return None


def validate_source_v0(item: Any, *, where: str = "source") -> dict[str, Any]:
    """Validate one external source against ``source-v0``.

    Errors are precise and path-addressed (``where`` names the position,
    e.g. ``sources[2]``) so an integrator can fix the exact field. This
    is the single complete source-v0 validator. Operator-invoked imports
    propagate its errors; evaluation catches the same errors and records
    them as fail-closed malformed_input reasons.
    """
    if not isinstance(item, dict):
        raise InputError(f"{where}: must be a JSON object")
    contract = item.get("contract", SOURCE_CONTRACT_VERSION)
    if contract != SOURCE_CONTRACT_VERSION:
        raise InputError(
            f"{where}.contract: unknown contract {contract!r}; "
            f"this version accepts {SOURCE_CONTRACT_VERSION!r}"
        )
    if "required" in item:
        raise InputError(
            f"{where}.required: the external source contract has no "
            "'required' field; required/advisory classification is "
            "policy-owned (list the source id in the policy's "
            "required_sources instead)"
        )
    for field in _REQUIRED_FIELDS:
        value = item.get(field)
        if not isinstance(value, str) or not value:
            raise InputError(
                f"{where}.{field}: must be a non-empty string"
            )
    digest = item["digest"]
    if not _DIGEST_RE.match(digest):
        raise InputError(
            f"{where}.digest: must match sha256:<64 lowercase hex>, "
            f"got {digest!r}"
        )
    for field in _OPTIONAL_STR_FIELDS:
        value = item.get(field)
        if value is not None and not isinstance(value, str):
            raise InputError(f"{where}.{field}: must be a string if present")
    unknown = sorted(set(item) - _KNOWN_FIELDS)
    if unknown:
        raise InputError(
            f"{where}: unknown field(s) {', '.join(unknown)}; "
            f"{SOURCE_CONTRACT_VERSION} fields are "
            f"{', '.join(sorted(_KNOWN_FIELDS))}"
        )
    normalized = dict(item)
    normalized["contract"] = SOURCE_CONTRACT_VERSION
    violation = contract_violation(normalized)
    if violation is not None:
        raise InputError(f"{where}: {violation}")
    return normalized


def load_external_sources(spec: str) -> list[dict[str, Any]]:
    """Load ``source-v0`` sources from a file path or ``-`` (stdin).

    The document may be a single source object or a list of them; every
    entry is validated strictly with a path-addressed error.
    """
    if spec == "-":
        text = sys.stdin.read()
        origin = "stdin"
    else:
        try:
            text = Path(spec).read_text(encoding="utf-8")
        except OSError as exc:
            raise InputError(f"cannot read source file {spec}: {exc}") from exc
        origin = spec
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"{origin}: invalid JSON: {exc}") from exc

    items = payload if isinstance(payload, list) else [payload]
    sources = []
    for position, item in enumerate(items):
        where = f"{origin}[{position}]" if isinstance(payload, list) else origin
        sources.append(validate_source_v0(item, where=where))
    return sources
