"""Safe path handling for operator-supplied output locations.

Output paths flow into shell contexts (for example the GitHub Action writes
``record=<path>`` into ``GITHUB_OUTPUT``), so control characters in a path
are not just unusual — they are an injection vector. Reject them before
anything is written.

When a workspace boundary is set (the GitHub Action sets
``AOS_GATE_WORKSPACE`` to the job workspace), output paths must also
resolve inside that boundary: traversal (``..``), absolute paths outside
the workspace, and symlinked escapes are all rejected after full path
resolution. Local CLI use without the environment variable stays
unbounded — the operator may write wherever their process can write.
"""

from __future__ import annotations

import os
from pathlib import Path

from .errors import InputError

WORKSPACE_ENV = "AOS_GATE_WORKSPACE"

_FORBIDDEN = ("\n", "\r", "\x00")


def workspace_boundary() -> Path | None:
    """Return the configured workspace boundary, if any."""
    raw = os.environ.get(WORKSPACE_ENV)
    return Path(raw) if raw and raw.strip() else None


def safe_output_path(raw: str, *, workspace: Path | None = None) -> Path:
    """Return a Path for an operator-supplied output location.

    Always rejects empty values and control characters (newline, carriage
    return, NUL). When ``workspace`` is given, the fully resolved target
    (symlinks included) must lie inside the resolved workspace; anything
    else is rejected.
    """
    if not raw or not raw.strip():
        raise InputError("output path must not be empty")
    for forbidden in _FORBIDDEN:
        if forbidden in raw:
            raise InputError(
                "output path must not contain control characters"
            )
    path = Path(raw)
    if workspace is None:
        return path

    boundary = workspace.resolve()
    target = path if path.is_absolute() else boundary / path
    resolved = target.resolve()
    if not resolved.is_relative_to(boundary):
        raise InputError(
            f"output path {raw!r} resolves outside the workspace boundary"
        )
    return resolved
