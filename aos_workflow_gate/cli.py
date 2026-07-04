"""Command-line interface for aos-workflow-gate.

``evaluate`` turns a signal bundle plus a policy into a decision record.
``verify`` recomputes a record's digests to detect tampering or a mismatched
source bundle. ``summarize`` renders a record as Markdown for maintainers.
In advisory mode the process exit code is always 0; only a policy in blocking
mode (or ``--enforce``) makes a ``BLOCK`` verdict fail.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import canonical
from .errors import InputError
from .evaluate import BLOCK, evaluate
from .evidence import build_record, verify_record
from .policy import load_policy
from .summarize import render_markdown
from .version import __version__


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "evaluate":
            return _cmd_evaluate(args)
        if args.command == "verify":
            return _cmd_verify(args)
        if args.command == "summarize":
            return _cmd_summarize(args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    parser.error("no command given")
    return 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aos-workflow-gate",
        description="Evidence-based workflow gate over CI, PR, scanner, "
        "and AI-agent signals.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    evaluate_parser = subparsers.add_parser(
        "evaluate", help="evaluate a signal bundle against a policy"
    )
    evaluate_parser.add_argument("--input", required=True, help="signal bundle JSON")
    evaluate_parser.add_argument("--policy", required=True, help="policy JSON or YAML")
    evaluate_parser.add_argument("--out", help="write the decision record here")
    evaluate_parser.add_argument(
        "--enforce",
        action="store_true",
        help="exit non-zero on BLOCK regardless of policy mode",
    )

    verify_parser = subparsers.add_parser(
        "verify", help="verify a decision record's integrity"
    )
    verify_parser.add_argument("--input", required=True, help="decision record JSON")
    verify_parser.add_argument(
        "--bundle", help="also check the record against this source bundle"
    )

    summarize_parser = subparsers.add_parser(
        "summarize", help="render a decision record as Markdown"
    )
    summarize_parser.add_argument(
        "--input", required=True, help="decision record JSON"
    )
    return parser


def _cmd_evaluate(args: argparse.Namespace) -> int:
    bundle = _load_json(args.input)
    policy = load_policy(Path(args.policy))
    decision = evaluate(bundle, policy)
    record = build_record(
        decision, policy=policy, input_bundle_digest=canonical.digest(bundle)
    )
    text = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if args.out:
        out_path = Path(args.out)
        if out_path.parent != Path(""):
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8", newline="\n")
        print(f"{decision.verdict}  {decision.summary}")
        print(f"record: {args.out}")
    else:
        sys.stdout.write(text)
        print(f"{decision.verdict}  {decision.summary}", file=sys.stderr)

    if (args.enforce or policy.mode == "blocking") and decision.verdict == BLOCK:
        return 1
    return 0


def _cmd_summarize(args: argparse.Namespace) -> int:
    record = _load_json(args.input)
    text, intact = render_markdown(record)
    sys.stdout.write(text)
    return 0 if intact else 1


def _cmd_verify(args: argparse.Namespace) -> int:
    record = _load_json(args.input)
    ok = verify_record(record)
    if ok and args.bundle and isinstance(record, dict):
        bundle = _load_json(args.bundle)
        ok = record.get("input_bundle_digest") == canonical.digest(bundle)
    print("OK" if ok else "TAMPERED")
    return 0 if ok else 1


def _load_json(path: str) -> Any:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON: {exc}") from exc
