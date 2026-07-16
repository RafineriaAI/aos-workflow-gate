"""Content-addressed verifier manifest.

A decision is only as trustworthy as the code that derived it. The
verifier manifest is a deterministic content address of the verifier
artifact: the sha256 of every packaged source file and policy pack,
keyed by its package-relative path, plus one digest over that mapping.
Text line endings are canonicalized to LF before hashing, so the same
packaged source has one identity on every supported platform. The
record carries the manifest digest, so **verifier
substitution is detectable**: a record claiming to come from manifest X
can be checked against any installation, and ``verify`` discloses a
mismatch instead of pretending the code was the same.

Boundary: this is content addressing, nothing more — no signing, no
provenance, and no claim about who authored or operated the verifier.
Records remain replayable across verifier versions; a different
manifest is disclosure, never a verdict.
"""

from __future__ import annotations

import copy
import hashlib
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import canonical

_FILE_HASH_RE = re.compile(r"^[0-9a-f]{64}$")

_PACKAGE_ROOT = Path(__file__).resolve().parent


def _packaged_files() -> list[Path]:
    files = sorted(_PACKAGE_ROOT.glob("*.py"))
    files += sorted((_PACKAGE_ROOT / "packs").glob("*.yml"))
    return files


def _canonical_content_digest(content: bytes) -> str:
    """Hash canonical text bytes, independent of platform line endings."""
    normalized = content.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(normalized).hexdigest()


@lru_cache(maxsize=1)
def _verifier_manifest() -> dict[str, Any]:
    """The manifest of the currently installed verifier."""
    files: dict[str, str] = {}
    for path in _packaged_files():
        rel = path.relative_to(_PACKAGE_ROOT).as_posix()
        files[rel] = _canonical_content_digest(path.read_bytes())
    return {
        "schema_version": "verifier-manifest-v0",
        "files": files,
        "manifest_digest": canonical.digest(files),
    }


def verifier_manifest() -> dict[str, Any]:
    """A detached copy of the currently installed verifier manifest."""
    return copy.deepcopy(_verifier_manifest())


def validate_verifier_manifest(value: Any) -> bool:
    """Validate structure and recompute the embedded manifest digest."""
    if not isinstance(value, dict):
        return False
    if value.get("schema_version") != "verifier-manifest-v0":
        return False
    if set(value) != {"schema_version", "files", "manifest_digest"}:
        return False
    files = value.get("files")
    claimed = value.get("manifest_digest")
    if not isinstance(files, dict) or not isinstance(claimed, str):
        return False
    for relative_path, file_hash in files.items():
        if not isinstance(relative_path, str) or not relative_path:
            return False
        if (
            relative_path.startswith("/")
            or "\\" in relative_path
            or any(
                part in ("", ".", "..")
                for part in relative_path.split("/")
            )
        ):
            return False
        if (
            not isinstance(file_hash, str)
            or _FILE_HASH_RE.fullmatch(file_hash) is None
        ):
            return False
    return claimed == canonical.digest(files)


def verifier_manifest_digest() -> str:
    """The content address of the currently installed verifier."""
    digest = verifier_manifest()["manifest_digest"]
    assert isinstance(digest, str)
    return digest
