"""aos-workflow-gate: evidence-based workflow gate around aos-kernel.

Turns CI, PR, scanner, and AI-agent signals into a deterministic
``PASS`` / ``WARN`` / ``BLOCK`` decision with a replayable, tamper-evident
evidence record. The output carries ``UNSIGNED_NOT_OFFICIAL`` verification
status: it is structure- and replay-checkable, not an official signed verdict.
"""

from __future__ import annotations

from .evaluate import BLOCK, PASS, WARN, Decision, Reason, Subject, evaluate
from .evidence import build_record, verify_record
from .policy import Policy, load_policy
from .version import __version__

__all__ = [
    "BLOCK",
    "PASS",
    "WARN",
    "Decision",
    "Policy",
    "Reason",
    "Subject",
    "__version__",
    "build_record",
    "evaluate",
    "load_policy",
    "verify_record",
]
