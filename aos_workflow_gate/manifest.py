"""Content-addressed verifier manifest.

A decision is only as trustworthy as the code that derived it. The
verifier manifest is a deterministic content address of the exact
verifier artifact: the sha256 of every packaged source file and policy
pack, keyed by its package-relative path, plus one digest over that
mapping. The record carries the manifest digest, so **verifier
substitution is detectable**: a record claiming to come from manifest X
can be checked against any installation, and ``verify`` discloses a
mismatch instead of pretending the code was the same.

Boundary: this is content addressing, nothing more — no signing, no
provenance, and no claim about who authored or operated the verifier.
Records remain replayable across verifier versions; a different
manifest is disclosure, never a verdict.
"""

from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from typing import Any

from . import canonical

_PACKAGE_ROOT = Path(__file__).resolve().parent


def _packaged_files() -> list[Path]:
    files = sorted(_PACKAGE_ROOT.glob("*.py"))
    files += sorted((_PACKAGE_ROOT / "packs").glob("*.yml"))
    return files


@lru_cache(maxsize=1)
def verifier_manifest() -> dict[str, Any]:
    """The manifest of the currently installed verifier."""
    files: dict[str, str] = {}
    for path in _packaged_files():
        rel = path.relative_to(_PACKAGE_ROOT).as_posix()
        files[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "schema_version": "verifier-manifest-v0",
        "files": files,
        "manifest_digest": canonical.digest(files),
    }


def verifier_manifest_digest() -> str:
    """The content address of the currently installed verifier."""
    digest = verifier_manifest()["manifest_digest"]
    assert isinstance(digest, str)
    return digest
