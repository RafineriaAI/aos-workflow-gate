"""Safe path handling for operator-supplied output locations.

Output paths flow into shell contexts (for example the GitHub Action writes
``record=<path>`` into ``GITHUB_OUTPUT``), so control characters in a path
are not just unusual — they are an injection vector. Reject them before
anything is written.
"""

from __future__ import annotations

from pathlib import Path

from .errors import InputError

_FORBIDDEN = ("\n", "\r", "\x00")


def safe_output_path(raw: str) -> Path:
    """Return a Path for an operator-supplied output location.

    Rejects empty values and control characters (newline, carriage return,
    NUL). Everything else is allowed: the operator may write wherever their
    process can write; the resolver guards against injection, not intent.
    """
    if not raw or not raw.strip():
        raise InputError("output path must not be empty")
    for forbidden in _FORBIDDEN:
        if forbidden in raw:
            raise InputError(
                "output path must not contain control characters"
            )
    return Path(raw)
