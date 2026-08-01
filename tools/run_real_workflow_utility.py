#!/usr/bin/env python3
"""Run the preregistered real-workflow benchmark without touching subject repos."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aos_workflow_gate.evidence import verify_record  # noqa: E402

DEFAULT_STUDY = ROOT / "benchmarks" / "real-workflow-utility"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _rewrite_ascii_json(path: Path) -> None:
    value = _read_json(path)
    path.write_text(
        json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
        encoding="ascii",
        newline="\n",
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-root", type=Path, default=DEFAULT_STUDY)
    parser.add_argument("--case", action="append", default=[])
    parser.add_argument("--allow-unauthenticated", action="store_true")
    return parser


def _selected_cases(
    selection: dict[str, Any], wanted: set[str]
) -> list[dict[str, Any]]:
    raw = selection.get("cases")
    if not isinstance(raw, list):
        raise ValueError("selection.cases must be a list")
    cases = [case for case in raw if isinstance(case, dict)]
    if wanted:
        cases = [case for case in cases if case.get("case_id") in wanted]
        missing = wanted - {str(case.get("case_id")) for case in cases}
        if missing:
            raise ValueError(f"unknown case id(s): {', '.join(sorted(missing))}")
    return cases


def _run_case(study_root: Path, case: dict[str, Any]) -> dict[str, Any]:
    case_id = str(case["case_id"])
    case_dir = study_root / "cases" / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    record = case_dir / "gate-decision.json"
    bundle = case_dir / "bundle.json"
    policy = case_dir / "policy.json"
    summary = case_dir / "summary.txt"
    execution = case_dir / "execution.json"

    for path in (record, bundle, policy):
        path.unlink(missing_ok=True)

    command = [
        sys.executable,
        "-m",
        "aos_workflow_gate",
        "check-pr",
        str(case["pr_url"]),
        "--mode",
        "advisory",
        "--wait-seconds",
        "0",
        "--out",
        str(record.relative_to(ROOT)),
        "--bundle-out",
        str(bundle.relative_to(ROOT)),
        "--policy-out",
        str(policy.relative_to(ROOT)),
    ]
    started = time.perf_counter()
    stderr = ""
    child_env = os.environ.copy()
    child_env["PYTHONUTF8"] = "1"
    child_env["PYTHONIOENCODING"] = "utf-8"
    try:
        process = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            timeout=300,
            env=child_env,
        )
        exit_code = process.returncode
        stdout = process.stdout.decode("utf-8", errors="replace")
        stderr = process.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired as error:
        exit_code = 124
        stdout = (error.stdout or b"").decode("utf-8", errors="replace")
        stderr = (error.stderr or b"").decode("utf-8", errors="replace")
        stderr += "\nbenchmark timeout after 300 seconds"
    elapsed = round(time.perf_counter() - started, 3)
    completed_at = (
        datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )
    summary.write_text(stdout, encoding="utf-8", newline="\n")
    for artifact in (record, bundle, policy):
        if artifact.is_file():
            _rewrite_ascii_json(artifact)
    record_valid = False
    if record.is_file():
        try:
            record_valid = verify_record(_read_json(record))
        except (OSError, ValueError, json.JSONDecodeError):
            record_valid = False
    if exit_code == 0 and not record_valid:
        exit_code = 3
        stderr += "\nrecord self-digest verification failed"

    result: dict[str, Any] = {
        "schema_version": "aos-real-workflow-execution/v0",
        "case_id": case_id,
        "started_from_pr_url": case["pr_url"],
        "selected_head_sha": case["head_sha"],
        "completed_at": completed_at,
        "exit_code": exit_code,
        "elapsed_seconds": elapsed,
        "token_present": bool(os.environ.get("GITHUB_TOKEN")),
        "stdout_encoding": "utf-8",
        "record_self_check": record_valid,
        "artifact_serialization": "ascii-safe-json",
    }
    if stderr.strip():
        result["stderr"] = stderr.strip()[:4000]
    _write_json(execution, result)
    return result


def main() -> int:
    args = _parser().parse_args()
    study_root = args.study_root.resolve()
    selection = _read_json(study_root / "selection.json")
    token_present = bool(os.environ.get("GITHUB_TOKEN"))
    if not token_present and not args.allow_unauthenticated:
        print(
            "GITHUB_TOKEN is required to prevent rate-limited partial observations; "
            "pass --allow-unauthenticated only for an intentional probe.",
            file=sys.stderr,
        )
        return 2

    wanted = {str(case_id) for case_id in args.case}
    results = [
        _run_case(study_root, case) for case in _selected_cases(selection, wanted)
    ]
    for result in results:
        print(
            f"{result['case_id']}: exit={result['exit_code']} "
            f"time={result['elapsed_seconds']}s"
        )
    return 0 if all(result["exit_code"] == 0 for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
