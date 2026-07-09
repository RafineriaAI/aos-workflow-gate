"""Deterministic serialization and digests.

All digests use a canonical JSON encoding so that the same logical value
always produces the same digest, independent of input formatting. This is
what makes decision records replayable and tamper-evident.

Normative recipe (docs/SOURCE_CONTRACT.md, with committed golden vectors
in examples/digest-vectors.json): the UTF-8 bytes of ``json.dumps(value,
ensure_ascii=False, sort_keys=True, separators=(",", ":"))``, hashed with
SHA-256 and prefixed ``sha256:``. Identity values should be strings,
integers, booleans, null, or containers of those; floats are legal JSON
but their textual form is implementation-sensitive, so exact values
belong in strings.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Encode a JSON-compatible value deterministically."""
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    """Return the lowercase hex SHA-256 of ``data``."""
    return hashlib.sha256(data).hexdigest()


def digest(value: Any) -> str:
    """Return a prefixed ``sha256:<hex>`` digest of a JSON-compatible value."""
    return "sha256:" + sha256_hex(canonical_json_bytes(value))
