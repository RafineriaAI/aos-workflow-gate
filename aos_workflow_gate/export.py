"""Export decision records as in-toto Statements.

``export`` wraps a verified decision record in an in-toto Statement (v1) so
existing supply-chain tooling can bind it to the gated commit and sign it
with keys the operator already holds (for example ``cosign sign-blob`` or
``cosign attest-blob``). The exported Statement is UNSIGNED; per the
standards boundary it must not be called an attestation until it is signed.
"""

from __future__ import annotations

import re
from typing import Any

from .errors import InputError
from .evidence import verify_record

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://github.com/RafineriaAI/aos-workflow-gate/decision-record/v0"

_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def build_statement(record: Any) -> dict[str, Any]:
    """Wrap a decision record in an in-toto Statement.

    The record must pass its self-digest check first; a tampered record must
    never be exported. The gated commit becomes the Statement subject with a
    ``gitCommit`` digest.
    """
    if not isinstance(record, dict):
        raise InputError("decision record must be a JSON object")
    if not verify_record(record):
        raise InputError(
            "record failed its self-digest check; refusing to export"
        )

    subject = record.get("subject")
    if not isinstance(subject, dict):
        raise InputError("decision record has no subject")
    repository = subject.get("repository")
    sha = subject.get("sha")
    if not isinstance(repository, str) or not repository:
        raise InputError("decision record subject has no repository")
    if not isinstance(sha, str) or not _GIT_SHA_RE.match(sha):
        raise InputError(
            "decision record subject has no 40-hex commit sha; "
            "an in-toto subject needs a gitCommit digest"
        )

    name = f"git+https://github.com/{repository}"
    ref = subject.get("ref")
    if isinstance(ref, str) and ref:
        name = f"{name}@{ref}"

    return {
        "_type": STATEMENT_TYPE,
        "subject": [{"name": name, "digest": {"gitCommit": sha}}],
        "predicateType": PREDICATE_TYPE,
        "predicate": record,
    }
