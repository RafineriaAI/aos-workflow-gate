"""Command-line interface for aos-workflow-gate.

``collect`` builds a signal bundle (and optionally an explicit advisory
policy) from the GitHub check-runs API for one commit.
``evaluate`` turns a signal bundle plus a policy into a decision record.
``verify`` recomputes a record's digests to detect tampering or a mismatched
source bundle. ``summarize`` renders a record as Markdown for maintainers.
``export`` wraps a verified record in an unsigned in-toto Statement.
In advisory mode the process exit code is always 0; only a policy in blocking
mode (or ``--enforce``) makes a ``BLOCK`` verdict fail.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from . import canonical
from .collect import (
    DEFAULT_API_URL,
    build_bundle,
    build_generated_policy,
    fetch_check_runs,
    resolve_github_context,
)
from .errors import InputError
from .evaluate import BLOCK, evaluate
from .evidence import build_record, verify_record
from .export import build_statement
from .paths import safe_output_path
from .policy import load_policy
from .summarize import render_markdown
from .version import __version__


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "collect":
            return _cmd_collect(args)
        if args.command == "evaluate":
            return _cmd_evaluate(args)
        if args.command == "verify":
            return _cmd_verify(args)
        if args.command == "summarize":
            return _cmd_summarize(args)
        if args.command == "export":
            return _cmd_export(args)
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

    collect_parser = subparsers.add_parser(
        "collect", help="build a signal bundle from the GitHub check-runs API"
    )
    collect_parser.add_argument(
        "--repository", help="owner/repo (defaults to the GitHub context)"
    )
    collect_parser.add_argument(
        "--sha", help="commit SHA (defaults to the GitHub context)"
    )
    collect_parser.add_argument("--ref", help="optional subject ref")
    collect_parser.add_argument(
        "--pull-request", type=int, help="optional subject pull request number"
    )
    collect_parser.add_argument(
        "--github-context",
        action="store_true",
        help="resolve repository/sha/ref/pull request from GitHub Actions "
        "environment variables",
    )
    collect_parser.add_argument(
        "--token-env",
        default="GITHUB_TOKEN",
        help="name of the environment variable holding the API token "
        "(default: GITHUB_TOKEN; unset means anonymous)",
    )
    collect_parser.add_argument(
        "--api-url",
        help="GitHub API base URL (default: GITHUB_API_URL env or "
        "https://api.github.com; set for GitHub Enterprise Server)",
    )
    collect_parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="check run name to exclude (repeatable)",
    )
    collect_parser.add_argument(
        "--require",
        action="append",
        default=[],
        help="collected check name to mark required in the generated "
        "policy (repeatable)",
    )
    collect_parser.add_argument(
        "--out", required=True, help="write the signal bundle here"
    )
    collect_parser.add_argument(
        "--policy-out",
        help="also write an explicit advisory policy covering every "
        "collected source",
    )

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

    export_parser = subparsers.add_parser(
        "export",
        help="wrap a verified decision record in an unsigned in-toto "
        "Statement",
    )
    export_parser.add_argument(
        "--input", required=True, help="decision record JSON"
    )
    export_parser.add_argument(
        "--format",
        choices=["in-toto-statement"],
        default="in-toto-statement",
        help="export format (default: in-toto-statement)",
    )
    export_parser.add_argument("--out", help="write the statement here")
    return parser


def _cmd_collect(args: argparse.Namespace) -> int:
    if args.github_context:
        context = resolve_github_context()
    else:
        context = {"repository": None, "sha": None, "ref": None, "pull_request": None}
    repository = args.repository or context["repository"]
    sha = args.sha or context["sha"]
    if not repository or not sha:
        raise InputError(
            "collect needs --repository and --sha, or --github-context"
        )
    token = os.environ.get(args.token_env) if args.token_env else None
    api_url = (
        args.api_url
        or os.environ.get("GITHUB_API_URL")
        or DEFAULT_API_URL
    )

    runs = fetch_check_runs(repository, sha, token=token, api_url=api_url)
    bundle = build_bundle(
        runs,
        repository=repository,
        sha=sha,
        ref=args.ref or context["ref"],
        pull_request=(
            args.pull_request
            if args.pull_request is not None
            else context["pull_request"]
        ),
        exclude=args.exclude,
        required=args.require,
    )
    _write_json(safe_output_path(args.out), bundle)
    print(f"collected {len(bundle['sources'])} completed check run(s)")
    print(f"bundle: {args.out}")

    if args.policy_out:
        policy = build_generated_policy(bundle, required=args.require)
        _write_json(safe_output_path(args.policy_out), policy)
        print(f"policy: {args.policy_out}")
    elif args.require:
        raise InputError("--require needs --policy-out")
    return 0


def _write_json(path: Path, value: dict[str, Any]) -> None:
    text = json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if path.parent != Path(""):
        path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def _cmd_evaluate(args: argparse.Namespace) -> int:
    bundle = _load_json(args.input)
    policy = load_policy(Path(args.policy))
    decision = evaluate(bundle, policy)
    record = build_record(
        decision, policy=policy, input_bundle_digest=canonical.digest(bundle)
    )
    text = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if args.out:
        out_path = safe_output_path(args.out)
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


def _cmd_export(args: argparse.Namespace) -> int:
    record = _load_json(args.input)
    statement = build_statement(record)
    text = json.dumps(statement, indent=2, ensure_ascii=False, sort_keys=True)
    text += "\n"
    if args.out:
        out_path = safe_output_path(args.out)
        if out_path.parent != Path(""):
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8", newline="\n")
        print(f"unsigned in-toto statement: {args.out}")
    else:
        sys.stdout.write(text)
    return 0


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
