"""File-based signal adapters.

Adapters are mechanical, never judgmental: they reduce a tool's output file
to a source with a fixed status mapping and a digest over the identity
subset actually used. Interpretation stays in the policy.

SARIF mapping contract (documented in docs/ADAPTERS.md):
``error``-level results -> status ``failure``; only ``warning``/``note``
results -> ``warning``; no results -> ``success``. A result without a level
counts as ``warning`` (the SARIF default).

Scorecard contract: presence-and-integrity signal only — status is
``success`` when the report parses; the aggregate score travels in the
summary and digest as data, not as a verdict.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .errors import InputError
from .source_contract import source_digest


def _load_json_file(path: Path, what: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"cannot read {what} {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"{what} {path} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise InputError(f"{what} {path} must be a JSON object")
    return payload


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "unknown"


def sarif_source(path: Path, source_id: str | None = None) -> dict[str, Any]:
    """Reduce a SARIF 2.1.0 file to a mechanical source."""
    payload = _load_json_file(path, "SARIF file")
    runs = payload.get("runs")
    if not isinstance(runs, list) or not runs:
        raise InputError(f"SARIF file {path} has no 'runs'")

    tool_name = "unknown"
    tool_version = None
    counts = {"error": 0, "warning": 0, "note": 0}
    for run in runs:
        if not isinstance(run, dict):
            continue
        driver = run.get("tool", {}).get("driver", {})
        if isinstance(driver, dict):
            if isinstance(driver.get("name"), str):
                tool_name = driver["name"]
            if isinstance(driver.get("version"), str):
                tool_version = driver["version"]
        results = run.get("results")
        if isinstance(results, list):
            for result in results:
                level = "warning"
                if isinstance(result, dict) and isinstance(
                    result.get("level"), str
                ):
                    level = result["level"]
                counts[level if level in counts else "warning"] += 1

    if counts["error"] > 0:
        status = "failure"
    elif counts["warning"] + counts["note"] > 0:
        status = "warning"
    else:
        status = "success"

    identity = {
        "tool": tool_name,
        "version": tool_version,
        "error_count": counts["error"],
        "warning_count": counts["warning"],
        "note_count": counts["note"],
        "status": status,
    }
    return {
        "id": source_id or f"sarif.{_slug(tool_name)}",
        "kind": "sarif_summary",
        "signal_source": "sarif_file",
        "status": status,
        "required": False,
        "summary": (
            f"SARIF: {counts['error']} error(s), {counts['warning']} "
            f"warning(s), {counts['note']} note(s) from {tool_name}."
        ),
        "identity": identity,
        "digest": source_digest(identity),
    }


def scorecard_source(path: Path, source_id: str | None = None) -> dict[str, Any]:
    """Reduce an OpenSSF Scorecard JSON report to a presence source."""
    payload = _load_json_file(path, "Scorecard report")
    score = payload.get("score")
    checks = payload.get("checks")
    if not isinstance(score, (int, float)):
        raise InputError(f"Scorecard report {path} has no numeric 'score'")
    check_count = len(checks) if isinstance(checks, list) else 0
    identity = {"score": score, "checks": check_count, "status": "success"}
    return {
        "id": source_id or "scorecard",
        "kind": "scorecard_summary",
        "signal_source": "scorecard_file",
        "status": "success",
        "required": False,
        "summary": (
            f"OpenSSF Scorecard aggregate score {score}/10 across "
            f"{check_count} check(s); presence-and-integrity signal only."
        ),
        "identity": identity,
        "digest": source_digest(identity),
    }
