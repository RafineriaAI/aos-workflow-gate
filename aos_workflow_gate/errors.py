"""Error types for aos-workflow-gate."""

from __future__ import annotations


class GateError(Exception):
    """Base error for aos-workflow-gate."""


class InputError(GateError):
    """Malformed or missing mandatory operator input.

    Raised for operator-controlled input that the gate cannot trust to
    proceed, such as a malformed policy. Untrusted *signal* data does not
    raise this; it is failed closed into a ``BLOCK`` decision record instead.
    """
