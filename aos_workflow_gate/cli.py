"""Command-line interface for aos-workflow-gate.

``collect`` builds a signal bundle (and optionally an explicit advisory
policy) from the GitHub check-runs API for one commit.
``evaluate`` turns a signal bundle plus a policy into a decision record.
``verify`` recomputes a record's digests to detect tampering or a mismatched
source bundle. ``summarize`` renders a record as Markdown for maintainers.
``export`` wraps a verified record in an unsigned in-toto Statement.
``preflight`` probes capabilities read-only and reports stable diagnostic
codes — readiness, never a verdict.
In advisory mode the process exit code is always 0; only a policy in blocking
mode (or ``--enforce``) makes a ``BLOCK`` verdict fail.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from importlib import resources
from pathlib import Path
from typing import Any

from . import canonical
from .adapters import sarif_source, scorecard_source
from .agent_action import (
    BOUNDED_DUPLICATE,
    FRESHNESS_UNVERIFIED,
    VALID,
    action_source,
    classify_action,
    compute_digests,
    fetch_branch_head,
    load_action_document,
)
from .bench import render_bench_report, verify_case
from .checkpr import (
    counterfactual_blockers,
    fetch_pr,
    parse_pr_url,
    rules_summary_source,
    status_sources,
)
from .collect import (
    DEFAULT_API_URL,
    Budget,
    build_bundle,
    build_generated_policy,
    collection_timestamp,
    github_context_snapshot,
    resolve_github_context,
    wait_for_required,
)
from .errors import InputError
from .evaluate import BLOCK, evaluate
from .evidence import (
    build_record,
    observation_from_bundle,
    subject_identity,
    verify_record,
)
from .export import build_statement
from .manifest import (
    validate_verifier_manifest,
    verifier_manifest_digest,
)
from .paths import safe_output_path, workspace_boundary
from .policy import load_policy
from .preflight import render_report, run_preflight
from .requirements import (
    PENDING,
    UNVERIFIABLE,
    legacy_status_source_ids,
    requirement_evidence,
    requirement_snapshot,
)
from .source_contract import load_external_sources
from .summarize import render_html, render_markdown, verify_bindings
from .verifier_change import analyze_verifier_change, fetch_pr_files
from .version import __version__
from .workflow_state import collect_workflow_visibility, fetch_workflow_runs


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
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "check-pr":
            return _cmd_check_pr(args)
        if args.command == "preflight":
            return _cmd_preflight(args)
        if args.command == "import":
            return _cmd_import(args)
        if args.command == "agent-action":
            return _cmd_agent_action(args)
        if args.command == "bench-verify":
            return _cmd_bench_verify(args)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(
            "hint: every failure symptom is mapped to its meaning and fix "
            "in docs/USER_FAQ.md (failure taxonomy)",
            file=sys.stderr,
        )
        return 2
    parser.error("no command given")
    return 2


_EXAMPLES = """\
examples:
  # one command: collect this commit's checks, gate, and summarize
  aos-workflow-gate run --github-context --require "ci / validate" \\
      --policy-pack minimal-pr-gate

  # the same, fully offline from committed files
  aos-workflow-gate run --input examples/github-pr-signal-bundle.json \\
      --policy policies/default.yml

  # replay a committed decision with no network
  aos-workflow-gate verify --input examples/gate-decision.json \\
      --bundle examples/github-pr-signal-bundle.json
"""


def resolve_policy_pack(name: str) -> Path:
    """Resolve a bundled policy pack by name to a filesystem path."""
    if not name.replace("-", "").isalnum():
        raise InputError(f"invalid policy pack name {name!r}")
    trav = resources.files("aos_workflow_gate").joinpath("packs", f"{name}.yml")
    path = Path(str(trav))
    if not path.is_file():
        packs = sorted(
            p.stem for p in Path(str(resources.files("aos_workflow_gate")
            .joinpath("packs"))).glob("*.yml")
        )
        raise InputError(
            f"unknown policy pack {name!r}; available: {', '.join(packs)}"
        )
    return path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="aos-workflow-gate",
        description="Evidence-based workflow gate over CI, PR, scanner, "
        "and AI-agent signals.",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")

    checkpr_parser = subparsers.add_parser(
        "check-pr",
        help="instant merge-protection check for a GitHub PR URL "
        "(read-only observer)",
    )
    checkpr_parser.add_argument(
        "pr_url", help="https://github.com/OWNER/REPO/pull/N (GHES too)"
    )
    checkpr_parser.add_argument(
        "--mode", choices=["advisory", "enforce"], default="advisory",
        help="enforce makes a BLOCK verdict exit 1 (default: advisory)",
    )
    checkpr_parser.add_argument(
        "--wait-seconds", type=float, default=0.0,
        help="poll until the rules' required checks complete (default 0)",
    )
    checkpr_parser.add_argument(
        "--poll-interval", type=float, default=10.0,
        help="seconds between polls (default 10)",
    )
    checkpr_parser.add_argument(
        "--out", default="gate-decision.json",
        help="decision record path (default: gate-decision.json)",
    )
    checkpr_parser.add_argument(
        "--bundle-out", default=".aos-gate/bundle.json",
        help="where to write the collected bundle",
    )
    checkpr_parser.add_argument(
        "--policy-out", default=".aos-gate/policy.json",
        help="where to write the generated policy",
    )
    checkpr_parser.add_argument(
        "--token-env", default="GITHUB_TOKEN",
        help="env var holding the API token (default GITHUB_TOKEN)",
    )
    checkpr_parser.add_argument(
        "--acknowledge-verifier-change",
        metavar="REASON",
        help="record an operator acknowledgement in evidence; it never "
        "suppresses or changes the verifier-change verdict",
    )

    preflight_parser = subparsers.add_parser(
        "preflight",
        help="read-only capability probes: what the token, environment, "
        "and target actually allow (diagnostic readiness, never a "
        "verdict)",
    )
    preflight_parser.add_argument(
        "--pr", help="https://github.com/OWNER/REPO/pull/N to probe"
    )
    preflight_parser.add_argument(
        "--repository", help="owner/repo to probe"
    )
    preflight_parser.add_argument(
        "--sha", help="commit to probe check runs and statuses on "
        "(default: PR head or the default branch)",
    )
    preflight_parser.add_argument(
        "--branch", help="branch to probe rules on (default: PR base or "
        "the default branch)",
    )
    preflight_parser.add_argument(
        "--github-context",
        action="store_true",
        help="probe the current GitHub Actions workflow context "
        "(workflow-scoped readiness report)",
    )
    preflight_parser.add_argument(
        "--json", action="store_true",
        help="print the full JSON report instead of the findings view",
    )
    preflight_parser.add_argument(
        "--verbose", action="store_true",
        help="also list every probe, not only the findings",
    )
    preflight_parser.add_argument(
        "--out", help="also write the JSON report to this path"
    )
    preflight_parser.add_argument(
        "--token-env", default="GITHUB_TOKEN",
        help="env var holding the API token (default GITHUB_TOKEN)",
    )
    preflight_parser.add_argument(
        "--api-url",
        help="GitHub API base URL (default: GITHUB_API_URL env or "
        "https://api.github.com)",
    )

    run_parser = subparsers.add_parser(
        "run",
        help="collect, evaluate, and summarize in one command",
        epilog=_EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    run_parser.add_argument(
        "--input", help="existing signal bundle JSON (skips collection)"
    )
    run_parser.add_argument(
        "--github-context",
        action="store_true",
        help="collect from the current GitHub Actions context "
        "(implies --github-context-match)",
    )
    run_parser.add_argument("--repository", help="owner/repo for collection")
    run_parser.add_argument("--sha", help="commit SHA for collection")
    run_parser.add_argument("--ref", help="optional subject ref")
    run_parser.add_argument(
        "--pull-request", type=int, help="optional subject pull request"
    )
    run_parser.add_argument(
        "--require", action="append", default=[],
        help="required check name (repeatable)",
    )
    run_parser.add_argument(
        "--exclude", action="append", default=[],
        help="check run name to exclude (repeatable)",
    )
    run_parser.add_argument(
        "--sarif", action="append", default=[], metavar="PATH",
        help="add a SARIF file as a source (repeatable)",
    )
    run_parser.add_argument(
        "--scorecard", metavar="PATH",
        help="add a Scorecard JSON report as a presence source",
    )
    run_parser.add_argument(
        "--policy", help="policy JSON or YAML (path)"
    )
    run_parser.add_argument(
        "--policy-pack",
        help="bundled starter policy by name (see docs/POLICY_PACKS.md)",
    )
    run_parser.add_argument(
        "--policy-digest",
        help="expected sha256:<hex> of the policy; mismatch exits 2",
    )
    run_parser.add_argument(
        "--mode", choices=["advisory", "enforce"], default="advisory",
        help="enforce makes a BLOCK verdict exit 1 (default: advisory)",
    )
    run_parser.add_argument(
        "--out", default="gate-decision.json",
        help="decision record path (default: gate-decision.json)",
    )
    run_parser.add_argument(
        "--bundle-out", default=".aos-gate/bundle.json",
        help="where to write the collected bundle",
    )
    run_parser.add_argument(
        "--policy-out", default=".aos-gate/policy.json",
        help="where to write the generated policy (generated mode only)",
    )
    run_parser.add_argument(
        "--wait-seconds", type=float, default=0.0,
        help=(
            "required-control polling budget; 0 uses 120 seconds for "
            "autodiscovery and no wait for explicit --require names"
        ),
    )
    run_parser.add_argument(
        "--poll-interval", type=float, default=10.0,
        help="seconds between polls (default 10)",
    )
    run_parser.add_argument(
        "--deadline-seconds", type=float, default=300.0,
        help="hard wall-clock limit for collection (default 300)",
    )
    run_parser.add_argument(
        "--max-api-calls", type=int, default=50,
        help="hard limit on API requests (default 50)",
    )
    run_parser.add_argument(
        "--token-env", default="GITHUB_TOKEN",
        help="env var holding the API token (default GITHUB_TOKEN)",
    )
    run_parser.add_argument(
        "--api-url",
        help="GitHub API base URL (default: GITHUB_API_URL env or "
        "https://api.github.com)",
    )
    run_parser.add_argument(
        "--acknowledge-verifier-change",
        metavar="REASON",
        help="record an operator acknowledgement in evidence; it never "
        "suppresses or changes the verifier-change verdict",
    )

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
        "--wait-seconds",
        type=float,
        default=0.0,
        help="poll until every --require check completes, up to this many "
        "seconds (default 0: no polling)",
    )
    collect_parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="seconds between polls while waiting (default 10)",
    )
    collect_parser.add_argument(
        "--deadline-seconds",
        type=float,
        default=300.0,
        help="hard wall-clock limit for the whole collection including "
        "retries and waits (default 300)",
    )
    collect_parser.add_argument(
        "--max-api-calls",
        type=int,
        default=50,
        help="hard limit on API requests for the whole collection "
        "(default 50)",
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
        "--sarif",
        action="append",
        default=[],
        metavar="PATH",
        help="add a SARIF 2.1.0 file as a mechanical source (repeatable); "
        "mapping contract in docs/ADAPTERS.md",
    )
    collect_parser.add_argument(
        "--scorecard",
        metavar="PATH",
        help="add an OpenSSF Scorecard JSON report as a presence source",
    )
    collect_parser.add_argument(
        "--out", required=True, help="write the signal bundle here"
    )
    collect_parser.add_argument(
        "--policy-out",
        help="also write an explicit advisory policy covering every "
        "collected source",
    )

    import_parser = subparsers.add_parser(
        "import",
        help="validate external source-v0 sources (file or stdin) and "
        "merge them into a signal bundle",
    )
    import_parser.add_argument(
        "--source",
        action="append",
        required=True,
        default=[],
        metavar="PATH_OR_-",
        help="source-v0 JSON document: one source object or a list; "
        "'-' reads stdin (repeatable; stdin at most once)",
    )
    import_parser.add_argument(
        "--input", help="existing signal bundle to extend"
    )
    import_parser.add_argument(
        "--repository", help="subject owner/repo when creating a fresh bundle"
    )
    import_parser.add_argument(
        "--sha", help="subject commit SHA when creating a fresh bundle"
    )
    import_parser.add_argument(
        "--ref", help="optional subject ref for a fresh bundle"
    )
    import_parser.add_argument(
        "--pull-request", type=int,
        help="optional subject pull request for a fresh bundle",
    )
    import_parser.add_argument(
        "--out", required=True, help="write the merged bundle here"
    )

    agent_parser = subparsers.add_parser(
        "agent-action",
        help="validate agent-action-v0 documents into source-v0 sources "
        "(valid/stale/tampered/subject_mismatch/bounded_duplicate)",
    )
    agent_parser.add_argument(
        "--input",
        action="append",
        required=True,
        default=[],
        metavar="DOC.json",
        help="agent action document (repeatable)",
    )
    agent_parser.add_argument(
        "--bundle",
        help="bundle for subject binding and bounded duplicate scope; "
        "with --out the sources are merged into it",
    )
    agent_parser.add_argument(
        "--live", action="store_true",
        help="staleness check against the live branch head",
    )
    agent_parser.add_argument(
        "--branch",
        help="branch for --live (default: the document's snapshot.branch)",
    )
    agent_parser.add_argument(
        "--pinned-base",
        help="staleness check against this pinned base SHA instead of "
        "the live head",
    )
    agent_parser.add_argument(
        "--out",
        help="write the merged bundle (with --bundle) or the sources "
        "JSON; default prints sources to stdout",
    )
    agent_parser.add_argument(
        "--token-env", default="GITHUB_TOKEN",
        help="env var holding the API token for --live",
    )
    agent_parser.add_argument(
        "--api-url",
        help="GitHub API base URL for --live (default: GITHUB_API_URL "
        "env or https://api.github.com)",
    )

    bench_parser = subparsers.add_parser(
        "bench-verify",
        help="validate and replay a recorded benchmark case directory "
        "(runs nothing; verified vs unverifiable stated per check)",
    )
    bench_parser.add_argument(
        "--case",
        action="append",
        required=True,
        default=[],
        metavar="DIR",
        help="benchmark case directory containing case.json (repeatable)",
    )
    bench_parser.add_argument(
        "--live", action="store_true",
        help="enable the Git ancestry probe via the compare API "
        "(otherwise ancestry is reported unverifiable)",
    )
    bench_parser.add_argument(
        "--json", action="store_true",
        help="print the JSON report(s) instead of the human view",
    )
    bench_parser.add_argument(
        "--token-env", default="GITHUB_TOKEN",
        help="env var holding the API token for --live",
    )
    bench_parser.add_argument(
        "--api-url",
        help="GitHub API base URL for --live (default: GITHUB_API_URL "
        "env or https://api.github.com)",
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
    evaluate_parser.add_argument(
        "--mode",
        choices=["advisory", "enforce"],
        help="explicit mode; enforce is equivalent to --enforce",
    )
    evaluate_parser.add_argument(
        "--policy-digest",
        help="expected sha256:<hex> digest of the policy; a mismatch is an "
        "operational error (exit 2), not a verdict",
    )
    evaluate_parser.add_argument(
        "--github-context-match",
        action="store_true",
        help="require the bundle subject to match the current GitHub "
        "Actions context (repository and commit); a mismatch is an "
        "operational error (exit 2), not a verdict",
    )

    verify_parser = subparsers.add_parser(
        "verify", help="verify a decision record's integrity"
    )
    verify_parser.add_argument("--input", required=True, help="decision record JSON")
    verify_parser.add_argument(
        "--bundle", help="also check the record against this source bundle"
    )

    summarize_parser = subparsers.add_parser(
        "summarize",
        help="render a decision record as Markdown or static HTML",
    )
    summarize_parser.add_argument(
        "--input", required=True, help="decision record JSON"
    )
    summarize_parser.add_argument(
        "--html", action="store_true",
        help="render a deterministic, self-contained static HTML "
        "evidence view instead of Markdown (same diagnosis, different "
        "view)",
    )
    summarize_parser.add_argument(
        "--out", help="write the rendered view here instead of stdout"
    )
    summarize_parser.add_argument(
        "--bundle",
        help="also verify the record against this bundle (bundle "
        "binding; with --policy, semantic replay too)",
    )
    summarize_parser.add_argument(
        "--policy",
        help="also verify the record's policy digest against this "
        "policy file (policy binding; with --bundle, semantic replay)",
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
    budget = Budget(
        deadline_seconds=args.deadline_seconds,
        max_api_calls=args.max_api_calls,
    )

    runs, truncated, incomplete, waited = wait_for_required(
        repository,
        sha,
        args.require,
        token=token,
        api_url=api_url,
        wait_seconds=args.wait_seconds,
        poll_interval=args.poll_interval,
        budget=budget,
    )
    status = "complete"
    if truncated:
        status = "truncated"
    elif incomplete:
        status = "wait_timeout"
    collection: dict[str, Any] = {
        "status": status,
        "observed_at": collection_timestamp(),
        "api_calls": budget.api_calls,
        "waited_seconds": round(waited, 1),
    }
    if args.github_context:
        collection["subject_context"] = {
            "repository": repository,
            "sha": sha,
        }
        snapshot = github_context_snapshot()
        collection["context_snapshot"] = snapshot
        collection["context_digest"] = canonical.digest(snapshot)
    if incomplete:
        collection["incomplete_required"] = incomplete
        print(
            "warning: wait budget ended with incomplete required "
            f"check(s): {', '.join(incomplete)}; they fail closed as "
            "missing",
            file=sys.stderr,
        )
    extra_sources = [sarif_source(Path(p)) for p in args.sarif]
    if args.scorecard:
        extra_sources.append(scorecard_source(Path(args.scorecard)))
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
        collection=collection,
        extra_sources=extra_sources,
    )
    _write_json(safe_output_path(args.out, workspace=workspace_boundary()), bundle)
    print(f"collected {len(bundle['sources'])} completed check run(s)")
    print(f"bundle: {args.out}")

    if args.policy_out:
        policy = build_generated_policy(bundle, required=args.require)
        _write_json(
            safe_output_path(args.policy_out, workspace=workspace_boundary()),
            policy,
        )
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
    if args.mode == "advisory" and args.enforce:
        raise InputError("--mode advisory conflicts with --enforce")
    if args.mode == "enforce":
        args.enforce = True
    bundle = _load_json(args.input)
    policy = load_policy(Path(args.policy))
    if args.policy_digest and policy.digest != args.policy_digest:
        raise InputError(
            f"policy digest mismatch: expected {args.policy_digest}, "
            f"loaded {policy.digest} (operational error, not a verdict)"
        )
    _check_context_integrity(bundle, require_match=args.github_context_match)
    decision = evaluate(bundle, policy)
    record = build_record(
        decision,
        policy=policy,
        input_bundle_digest=canonical.digest(bundle),
        can_block=bool(args.enforce or policy.mode == "blocking"),
        observation=observation_from_bundle(bundle),
    )
    text = json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n"

    if args.out:
        out_path = safe_output_path(args.out, workspace=workspace_boundary())
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


def _cmd_run(args: argparse.Namespace) -> int:
    """Collect, evaluate, and summarize in one command."""
    if args.policy and args.policy_pack:
        raise InputError("use either --policy or --policy-pack, not both")

    workspace = workspace_boundary()
    if args.input:
        bundle = _load_json(args.input)
    else:
        if args.github_context:
            context = resolve_github_context()
        else:
            context = {
                "repository": None, "sha": None,
                "ref": None, "pull_request": None,
            }
        repository = args.repository or context["repository"]
        sha = args.sha or context["sha"]
        if not repository or not sha:
            raise InputError(
                "run needs --input, or --repository and --sha, or "
                "--github-context"
            )
        token = os.environ.get(args.token_env) if args.token_env else None
        api_url = (
            args.api_url
            or os.environ.get("GITHUB_API_URL")
            or DEFAULT_API_URL
        )
        budget = Budget(
            deadline_seconds=args.deadline_seconds,
            max_api_calls=args.max_api_calls,
        )

        # requirement discovery: with a GitHub context and no operator
        # inputs, the gate reads what GitHub itself requires (rulesets,
        # classic protection fallback) instead of guessing from names
        discovered: dict[str, Any] | None = None
        if (
            args.github_context
            and not args.require
            and not args.policy
            and not args.policy_pack
        ):
            # PR events: the base branch; merge_group events: the queue's
            # base branch (never the ephemeral queue ref); push: the ref
            branch = context.get("branch")
            if branch:
                parts = repository.rstrip("/").rsplit("/", 2)
                slug = (
                    "/".join(parts[-2:]) if len(parts) >= 2 else repository
                )
                try:
                    discovered = requirement_snapshot(
                        api_url=api_url,
                        slug=slug,
                        repository=repository,
                        sha=sha,
                        branch=branch,
                        token=token,
                        budget=budget,
                        # default stabilization: discovered requirements
                        # are worth a bounded wait even when the
                        # operator configured none
                        wait_seconds=(
                            args.wait_seconds
                            if args.wait_seconds > 0
                            else 120.0
                        ),
                        poll_interval=args.poll_interval,
                        exclude_self=True,
                    )
                except InputError as exc:
                    print(
                        "Degraded (can_continue: yes): requirement "
                        f"discovery unavailable ({exc}); continuing in "
                        "name-based zero-config mode.",
                        file=sys.stderr,
                    )

        status_srcs: list[dict[str, Any]] = []
        if discovered is not None:
            runs = discovered["qualifying_runs"]
            truncated = discovered["truncated"]
            incomplete = discovered["incomplete_required"]
            waited = discovered["waited_seconds"]
            required_ids: list[str] = discovered["required_ids"]
            run_source_ids = {
                run.get("_aos_source_id", run.get("name"))
                for run in runs
                if isinstance(
                    run.get("_aos_source_id", run.get("name")), str
                )
            }
            status_srcs, _skipped = status_sources(
                discovered["statuses"],
                exclude_contexts={str(name) for name in run_source_ids},
                source_ids_by_context=legacy_status_source_ids(
                    discovered["controls"]
                ),
            )
        else:
            runs, truncated, incomplete, waited = wait_for_required(
                repository, sha, args.require,
                token=token, api_url=api_url,
                wait_seconds=args.wait_seconds,
                poll_interval=args.poll_interval,
                budget=budget,
            )
            required_ids = list(args.require)
        status = "complete"
        if truncated:
            status = "truncated"
        elif discovered is not None and discovered.get(
            "subject_mismatch_runs"
        ):
            status = "subject_mismatch"
        elif incomplete:
            status = "wait_timeout"
        collection: dict[str, Any] = {
            "status": status,
            "observed_at": collection_timestamp(),
            "api_calls": budget.api_calls,
            "waited_seconds": round(waited, 1),
        }
        if incomplete:
            collection["incomplete_required"] = incomplete
        if discovered is not None:
            collection["observation_scope"] = discovered[
                "observation_scope"
            ]
            collection["required_controls"] = [
                {
                    "context": control["context"],
                    "integration_id": control.get("integration_id"),
                    "source_id": control["source_id"],
                }
                for control in discovered["controls"]
            ]
            collection["requirements"] = requirement_evidence(
                discovered["controls"]
            )
            collection["rules_digest"] = discovered["rules_digest"]
            collection["protection_digest"] = discovered[
                "protection_digest"
            ]
            collection["github_baseline"] = discovered["github_baseline"]
            collection["protection_source"] = discovered[
                "protection_source"
            ]
            if discovered["self_reference_excluded"]:
                collection["self_reference_excluded"] = discovered[
                    "self_reference_excluded"
                ]
            if discovered.get("classic_protection_note"):
                collection["classic_protection_note"] = discovered[
                    "classic_protection_note"
                ]
            if discovered.get("statuses_unverifiable"):
                collection["statuses_unverifiable"] = discovered[
                    "statuses_unverifiable"
                ]
            if discovered.get("subject_mismatch_runs"):
                collection["subject_mismatch_runs"] = discovered[
                    "subject_mismatch_runs"
                ]
        if args.github_context:
            collection["subject_context"] = {
                "repository": repository,
                "sha": sha,
            }
            snapshot = github_context_snapshot()
            collection["context_snapshot"] = snapshot
            collection["context_digest"] = canonical.digest(snapshot)
        collection["workflow_visibility"] = collect_workflow_visibility(
            repository, sha, token=token, api_url=api_url, budget=budget
        )
        _print_workflow_visibility(collection["workflow_visibility"])
        pr_number = (
            args.pull_request
            if args.pull_request is not None
            else context["pull_request"]
        )
        if pr_number is not None:
            collection["verifier_change"] = _collect_verifier_change(
                repository=repository,
                sha=sha,
                pr_number=pr_number,
                check_runs=runs,
                token=token,
                api_url=api_url,
                budget=budget,
                acknowledged=args.acknowledge_verifier_change,
                policy_path=args.policy,
            )
            _print_verifier_change(collection["verifier_change"])
        extra_sources = [sarif_source(Path(p)) for p in args.sarif]
        if args.scorecard:
            extra_sources.append(scorecard_source(Path(args.scorecard)))
        extra_sources.extend(status_srcs)
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
            required=required_ids,
            collection=collection,
            extra_sources=extra_sources,
        )
        _write_json(safe_output_path(args.bundle_out, workspace=workspace), bundle)
        if discovered is not None:
            print(
                f"Discovered {len(required_ids)} required status "
                f"check(s) from {discovered['protection_source']} on "
                f"'{discovered['branch']}'."
            )
            if discovered["self_reference_excluded"]:
                print(
                    "Self-reference: excluded the gate's own check(s) "
                    "from waiting and grading: "
                    + ", ".join(discovered["self_reference_excluded"])
                )
            if discovered.get("classic_protection_note"):
                print(f"Note: {discovered['classic_protection_note']}")

    if args.policy:
        policy_path = Path(args.policy)
    elif args.policy_pack:
        policy_path = resolve_policy_pack(args.policy_pack)
    elif not args.input:
        # discovered requirements fail closed on the record (a missing
        # required check must BLOCK, not error out); operator-typed
        # --require keeps the early typo-catching error
        generated = build_generated_policy(
            bundle,
            required=required_ids,
            allow_missing_required=discovered is not None,
            required_status_semantics=(
                "github" if discovered is not None else None
            ),
            # A missing repository gate is durable repository-level
            # coverage evidence, not a fresh per-PR alert in recurring
            # zero-config Action runs.
            no_required_sources_severity=(
                "PASS" if discovered is not None else "WARN"
            ),
        )
        generated_path = safe_output_path(args.policy_out, workspace=workspace)
        _write_json(generated_path, generated)
        policy_path = generated_path
    else:
        raise InputError("run with --input needs --policy or --policy-pack")

    policy = load_policy(policy_path)
    if args.policy_digest and policy.digest != args.policy_digest:
        raise InputError(
            f"policy digest mismatch: expected {args.policy_digest}, "
            f"loaded {policy.digest} (operational error, not a verdict)"
        )
    _check_context_integrity(bundle, require_match=args.github_context)

    decision = evaluate(bundle, policy)
    enforce = args.mode == "enforce"
    record = build_record(
        decision,
        policy=policy,
        input_bundle_digest=canonical.digest(bundle),
        can_block=bool(enforce or policy.mode == "blocking"),
        observation=observation_from_bundle(bundle),
    )
    out_path = safe_output_path(args.out, workspace=workspace)
    if out_path.parent != Path(""):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    text, _ = render_markdown(record)
    print(f"{decision.verdict}  {decision.summary}")
    print(f"record: {args.out}")
    print()
    sys.stdout.write(text)
    if (enforce or policy.mode == "blocking") and decision.verdict == BLOCK:
        return 1
    return 0


def _verifier_change_unavailable(
    *, repository: str, sha: str, pr_number: int, detail: str
) -> dict[str, Any]:
    return {
        "analyzed": False,
        "available": False,
        "unavailable": detail,
        "subject": {
            "repository": repository,
            "pull_request": pr_number,
            "head_sha": sha,
        },
    }


def _collect_verifier_change(
    *,
    repository: str,
    sha: str,
    pr_number: int,
    check_runs: list[dict[str, Any]],
    token: str | None,
    api_url: str,
    budget: Budget,
    acknowledged: str | None,
    policy_path: str | None = None,
    expected_base_sha: str | None = None,
) -> dict[str, Any]:
    """Collect complete, SHA-bound facts for the mechanical analysis.

    The PR metadata is read before and after file enumeration. A moving
    head/base, an incomplete file list, or truncated workflow runs makes
    this evidence unavailable; evaluation then emits a policy-visible
    reason instead of silently accepting a clean result.
    """
    parts = repository.rstrip("/").rsplit("/", 2)
    slug = "/".join(parts[-2:]) if len(parts) >= 2 else repository

    def unavailable(detail: str) -> dict[str, Any]:
        return _verifier_change_unavailable(
            repository=repository,
            sha=sha,
            pr_number=pr_number,
            detail=detail,
        )

    try:
        before = fetch_pr(
            api_url, slug, pr_number, token=token, budget=budget
        )
        if before["head_sha"] != sha:
            return unavailable(
                "pull request head changed before verifier analysis: "
                f"expected {sha}, observed {before['head_sha']}"
            )
        if (
            expected_base_sha is not None
            and before["base_sha"] != expected_base_sha
        ):
            return unavailable(
                "pull request base changed before verifier analysis: "
                f"expected {expected_base_sha}, observed {before['base_sha']}"
            )

        changed_paths, files_truncated = fetch_pr_files(
            api_url, slug, pr_number, token=token, budget=budget
        )
        if files_truncated:
            return unavailable(
                "pull request file enumeration reached GitHub's "
                "3,000-file response ceiling"
            )

        workflow_runs, runs_truncated = fetch_workflow_runs(
            repository, sha, token=token, api_url=api_url, budget=budget
        )
        if runs_truncated:
            return unavailable(
                "workflow-run enumeration was truncated for the head SHA"
            )

        after = fetch_pr(
            api_url, slug, pr_number, token=token, budget=budget
        )
    except InputError as exc:
        return unavailable(str(exc))

    if (
        before["head_sha"] != after["head_sha"]
        or before["base_sha"] != after["base_sha"]
    ):
        return unavailable(
            "pull request head/base changed during verifier analysis"
        )

    extra_policy = [Path(policy_path).as_posix()] if policy_path else None
    analysis = analyze_verifier_change(
        changed_paths,
        workflow_runs,
        check_runs,
        bot_author=bool(before.get("author_bot")),
        acknowledged=acknowledged,
        extra_policy_paths=extra_policy,
    )
    analysis["available"] = True
    analysis["complete"] = True
    analysis["subject"] = {
        "repository": repository,
        "pull_request": pr_number,
        "head_sha": before["head_sha"],
        "base_sha": before["base_sha"],
    }
    return analysis


def _print_verifier_change(analysis: dict[str, Any]) -> None:
    if not analysis.get("analyzed"):
        print(
            "Verifier change: analysis unavailable; "
            f"{analysis.get('unavailable', 'unknown reason')}. "
            "The limitation is recorded and policy-visible."
        )
        return
    affected = analysis.get("non_independent_sources") or []
    if analysis.get("acknowledged"):
        print(
            "Verifier change: operator acknowledgement recorded; "
            "it does not alter the verdict."
        )
    if analysis.get("routine_bump_excluded"):
        print(
            "Verifier change: routine dependency bump excluded "
            "(recorded in the bundle)."
        )
        return
    if affected:
        shown = ", ".join(str(name) for name in affected[:3])
        print(
            f"Verifier change: {len(affected)} source(s) were produced "
            f"by a workflow this change itself modifies: {shown}. "
            "Advisory by default; see collection.verifier_change."
        )


def _print_workflow_visibility(report: dict[str, Any]) -> None:
    """One line, only when there is something the dashboard cannot show."""
    if not report.get("available"):
        print(
            "Workflow visibility unavailable (recorded in the bundle): "
            f"{report.get('unavailable', 'unknown reason')}"
        )
        return
    not_started = report.get("not_started") or []
    if not not_started:
        return
    awaiting = sum(
        1 for unit in not_started if unit.get("state") == "action_required"
    )
    names = ", ".join(
        str(
            unit.get("workflow_name")
            or unit.get("app_slug")
            or unit.get("check_suite_id")
        )
        for unit in not_started[:3]
    )
    detail = f" ({awaiting} awaiting approval/action)" if awaiting else ""
    print(
        f"Workflow visibility: {len(not_started)} execution unit(s) on "
        f"this commit have not started{detail}: {names}"
    )


def _cmd_check_pr(args: argparse.Namespace) -> int:
    """Instant merge-protection check: PR URL in, decision record out."""
    coords = parse_pr_url(args.pr_url)
    token = os.environ.get(args.token_env) if args.token_env else None
    budget = Budget()
    workspace = workspace_boundary()

    pr = fetch_pr(
        coords["api_url"], coords["slug"], coords["number"],
        token=token, budget=budget,
    )
    snapshot = requirement_snapshot(
        api_url=coords["api_url"],
        slug=coords["slug"],
        repository=coords["repository"],
        sha=pr["head_sha"],
        branch=pr["base_ref"],
        token=token,
        budget=budget,
        wait_seconds=args.wait_seconds,
        poll_interval=args.poll_interval,
    )
    rules = snapshot["rules"]
    controls = snapshot["controls"]
    required_ids = snapshot["required_ids"]
    runs = snapshot["qualifying_runs"]
    incomplete = snapshot["incomplete_required"]

    run_source_ids = {
        run.get("_aos_source_id", run.get("name"))
        for run in runs
        if isinstance(run.get("_aos_source_id", run.get("name")), str)
    }
    status_srcs, skipped_contexts = status_sources(
        snapshot["statuses"],
        exclude_contexts={str(n) for n in run_source_ids},
        source_ids_by_context=legacy_status_source_ids(controls),
    )
    still_running = sorted(
        str(control["source_id"]) for control in controls
        if control["state"] == PENDING
    )
    unverifiable = sorted(
        str(control["source_id"]) for control in controls
        if control["state"] == UNVERIFIABLE
    )
    status = "complete"
    if snapshot["truncated"]:
        status = "truncated"
    elif snapshot.get("subject_mismatch_runs"):
        status = "subject_mismatch"
    elif incomplete:
        status = "wait_timeout"
    collection: dict[str, Any] = {
        "status": status,
        "observed_at": collection_timestamp(),
        "observation_scope": snapshot["observation_scope"],
        "api_calls": budget.api_calls,
        "waited_seconds": round(snapshot["waited_seconds"], 1),
        "rules_digest": snapshot["rules_digest"],
        "protection_digest": snapshot["protection_digest"],
        "protection_source": snapshot["protection_source"],
        "github_baseline": snapshot["github_baseline"],
        "required_controls": [
            {
                "context": control["context"],
                "source_id": control["source_id"],
                "integration_id": control.get("integration_id"),
            }
            for control in controls
        ],
        "requirements": requirement_evidence(controls),
        "strict_up_to_date_required": snapshot["strict_up_to_date_required"],
        "pr": {
            "state": pr["state"],
            "merged": pr["merged"],
            "draft": pr["draft"],
            "from_fork": pr["from_fork"],
        },
    }
    collection["workflow_visibility"] = collect_workflow_visibility(
        coords["repository"], pr["head_sha"],
        token=token, api_url=coords["api_url"], budget=budget,
    )
    collection["verifier_change"] = _collect_verifier_change(
        repository=coords["repository"],
        sha=pr["head_sha"],
        pr_number=coords["number"],
        check_runs=snapshot["runs"],
        token=token,
        api_url=coords["api_url"],
        budget=budget,
        acknowledged=args.acknowledge_verifier_change,
        expected_base_sha=pr["base_sha"],
    )
    if incomplete:
        collection["incomplete_required"] = incomplete
    if still_running:
        collection["pending_required"] = still_running
    if unverifiable:
        collection["unverifiable_required"] = unverifiable
    if snapshot.get("statuses_unverifiable"):
        collection["statuses_unverifiable"] = snapshot[
            "statuses_unverifiable"
        ]
    if snapshot.get("subject_mismatch_runs"):
        collection["subject_mismatch_runs"] = snapshot[
            "subject_mismatch_runs"
        ]
    if skipped_contexts:
        collection["duplicate_status_contexts"] = skipped_contexts
    bundle = build_bundle(
        runs,
        repository=coords["repository"],
        sha=pr["head_sha"],
        ref=f"refs/pull/{coords['number']}/head",
        pull_request=coords["number"],
        required=required_ids,
        collection=collection,
        extra_sources=[rules_summary_source(rules)] + status_srcs,
    )
    would_block = counterfactual_blockers(bundle["sources"])
    if would_block:
        bundle["collection"]["counterfactual_blockers"] = would_block
    _write_json(safe_output_path(args.bundle_out, workspace=workspace), bundle)

    policy = build_generated_policy(
        bundle,
        required=required_ids,
        allow_missing_required=True,
        required_status_semantics="github",
    )
    policy_path = safe_output_path(args.policy_out, workspace=workspace)
    _write_json(policy_path, policy)
    loaded = load_policy(policy_path)

    decision = evaluate(bundle, loaded)
    enforce = args.mode == "enforce"
    record = build_record(
        decision,
        policy=loaded,
        input_bundle_digest=canonical.digest(bundle),
        can_block=enforce,
        observation=observation_from_bundle(bundle),
    )
    out_path = safe_output_path(args.out, workspace=workspace)
    if out_path.parent != Path(""):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(record, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(f"{decision.verdict}  {decision.summary}")
    print(f"record: {args.out}")
    print(
        f"Merge protection: {len(required_ids)} required status check(s) "
        f"enforced by {snapshot['protection_source']} on "
        f"'{pr['base_ref']}'."
    )
    baseline = snapshot["github_baseline"]
    if baseline == "clear" and decision.verdict != "PASS":
        print(
            "GitHub baseline: every required status check would pass "
            "under GitHub's own semantics (neutral and skipped count as "
            "passing there); this gate grades the evidence instead - "
            "the divergence is recorded per control in "
            "collection.requirements."
        )
    elif baseline != "clear":
        print(
            f"GitHub baseline (status checks only): {baseline}."
        )
    if not required_ids:
        print(
            "Effect: nothing in the branch rules blocks this merge on "
            "status checks; the record is evidence, not enforcement."
        )
    if pr["merged"] or pr["state"] == "closed":
        print(
            "Retrospective: this pull request is "
            + ("merged" if pr["merged"] else "closed")
            + "; the rules observed are CURRENT state, not merge-time "
            "state (compare rules_digest across records to detect drift)."
        )
    if pr["draft"]:
        print("Draft PR: checks may be intentionally deferred.")
    if pr["from_fork"]:
        print(
            "Fork PR: some checks may not run for forks by repository "
            "policy."
        )
    if collection.get("strict_up_to_date_required"):
        print(
            "Strict rules: GitHub additionally requires the branch to be "
            "up to date with the base; this verdict is head-SHA-scoped "
            "and does not check that."
        )
    _print_workflow_visibility(collection["workflow_visibility"])
    _print_verifier_change(collection["verifier_change"])
    if still_running:
        print(
            "Still running (fails closed as missing until finished; use "
            "--wait-seconds): " + ", ".join(still_running)
        )
    if unverifiable:
        print(
            "Unverifiable (cannot be shown to satisfy the requirement - "
            "app-bound requirement identity mismatch or unreadable "
            "stream; fails closed as missing): " + ", ".join(unverifiable)
        )
    if snapshot.get("statuses_unverifiable"):
        print(
            "Degraded (can_continue: yes): legacy commit statuses could "
            "not be read and are recorded as unverifiable evidence in "
            "the bundle collection."
        )
    if would_block:
        print(
            "Counterfactual: would BLOCK if required: "
            + ", ".join(would_block)
        )
    print(
        "Note: this check is a read-only observer of status-check rules "
        "and not a full merge-readiness assessment; reviews and other "
        "rule types are summarized in 'branch.rules' but not evaluated, "
        "and rule bypass actors are not observable from the public API."
    )
    print()
    text, _ = render_markdown(record)
    sys.stdout.write(text)
    if enforce and decision.verdict == BLOCK:
        return 1
    return 0


def _cmd_preflight(args: argparse.Namespace) -> int:
    """Diagnostic readiness probes; exit 0 ready, 1 degraded, 2 no probe.

    Exit 1 here means "a probed capability is unavailable" — a readiness
    statement, never a policy verdict (this command produces none).
    """
    token = os.environ.get(args.token_env) if args.token_env else None
    report = run_preflight(
        pr_url=args.pr,
        repository=args.repository,
        sha=args.sha,
        branch=args.branch,
        github_context=args.github_context,
        token=token,
        api_url=args.api_url,
    )
    if args.out:
        _write_json(
            safe_output_path(args.out, workspace=workspace_boundary()), report
        )
    if args.json:
        text = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
        sys.stdout.write(text + "\n")
    else:
        sys.stdout.write(render_report(report, verbose=args.verbose))
    return 0 if report["ready"] else 1


def _cmd_import(args: argparse.Namespace) -> int:
    """Merge validated external source-v0 sources into a bundle.

    Validation is strict with path-addressed errors (operator-invoked
    tooling); the sources carry no ``required`` field — classification
    stays policy-owned at evaluation time.
    """
    if args.source.count("-") > 1:
        raise InputError("'-' (stdin) may be used at most once")
    imported: list[dict[str, Any]] = []
    for spec in args.source:
        imported.extend(load_external_sources(spec))

    if args.input:
        bundle = _load_json(args.input)
        if not isinstance(bundle, dict) or not isinstance(
            bundle.get("sources"), list
        ):
            raise InputError(f"{args.input} is not a signal bundle")
    else:
        if not args.repository or not args.sha:
            raise InputError("import needs --input, or --repository and --sha")
        subject: dict[str, Any] = {
            "repository": args.repository, "sha": args.sha,
        }
        if args.ref:
            subject["ref"] = args.ref
        if args.pull_request is not None:
            subject["pull_request"] = args.pull_request
        bundle = {
            "schema_version": "draft-0",
            "subject": subject,
            "sources": [],
        }

    existing_ids = {
        source.get("id")
        for source in bundle["sources"]
        if isinstance(source, dict)
    }
    for source in imported:
        if source["id"] in existing_ids:
            raise InputError(
                f"imported source id {source['id']!r} collides with an "
                "existing source; pass a distinct id"
            )
        existing_ids.add(source["id"])
        bundle["sources"].append(source)
    bundle["sources"].sort(key=lambda source: str(source.get("id")))

    collection = bundle.setdefault("collection", {})
    if isinstance(collection, dict):
        imported_ids = sorted(source["id"] for source in imported)
        prior = collection.get("imported_sources")
        if isinstance(prior, list):
            imported_ids = sorted(set(prior) | set(imported_ids))
        collection["imported_sources"] = imported_ids

    _write_json(safe_output_path(args.out, workspace=workspace_boundary()), bundle)
    print(
        f"imported {len(imported)} source(s) under the source-v0 contract"
    )
    print(f"bundle: {args.out}")
    return 0


def _cmd_agent_action(args: argparse.Namespace) -> int:
    """Validate agent action documents into source-v0 sources.

    The adapter has no execution authority and makes no semantic
    approval claim: a 'success' status asserts structural integrity and
    binding only. Duplicate detection is bounded to this invocation and
    the given bundle — never global.
    """
    if args.live and args.pinned_base:
        raise InputError("use either --live or --pinned-base, not both")
    if args.pinned_base is not None and not re.match(
        r"^[0-9a-f]{40}$", args.pinned_base
    ):
        raise InputError("--pinned-base must be a 40-char lowercase hex SHA")

    docs = [load_action_document(Path(path)) for path in args.input]

    bundle: dict[str, Any] | None = None
    bundle_subject: dict[str, Any] | None = None
    existing_ids: set[str] = set()
    agent_ids: set[str] = set()
    if args.bundle:
        loaded = _load_json(args.bundle)
        if not isinstance(loaded, dict) or not isinstance(
            loaded.get("sources"), list
        ):
            raise InputError(f"{args.bundle} is not a signal bundle")
        bundle = loaded
        subject = bundle.get("subject")
        bundle_subject = subject if isinstance(subject, dict) else None
        for source in bundle["sources"]:
            if not isinstance(source, dict):
                continue
            existing_ids.add(str(source.get("id")))
            if source.get("kind") == "agent_action":
                agent_ids.add(str(source.get("id")))

    mode = "live" if args.live else ("pinned" if args.pinned_base else "none")
    token = os.environ.get(args.token_env) if args.token_env else None
    api_url = (
        args.api_url or os.environ.get("GITHUB_API_URL") or DEFAULT_API_URL
    )
    budget = Budget()
    head_cache: dict[tuple[str, str], str] = {}

    sources: list[dict[str, Any]] = []
    seen_digests: set[str] = set()
    first_id_of: dict[str, str] = {}
    for doc in docs:
        observed_base: str | None = None
        if args.pinned_base:
            observed_base = args.pinned_base
        elif args.live:
            snapshot = doc.get("snapshot")
            branch = args.branch or (
                snapshot.get("branch") if isinstance(snapshot, dict) else None
            )
            if not isinstance(branch, str) or not branch:
                raise InputError(
                    "--live needs --branch (or snapshot.branch in the "
                    "document)"
                )
            key = (doc["repository"], branch)
            if key not in head_cache:
                head_cache[key] = fetch_branch_head(
                    doc["repository"], branch,
                    token=token, api_url=api_url, budget=budget,
                )
            observed_base = head_cache[key]

        computed = compute_digests(doc)
        base_id = f"agent.action.{computed['action'][7:19]}"
        state, explanation = classify_action(
            doc,
            bundle_subject=bundle_subject,
            observed_base=observed_base,
            validation_mode=mode,
            seen_action_digests=seen_digests,
            duplicate_of=first_id_of.get(computed["action"]),
        )
        if state in (VALID, FRESHNESS_UNVERIFIED) and base_id in agent_ids:
            state = BOUNDED_DUPLICATE
            explanation = (
                "Agent action bounded duplicate: same action digest as "
                f"bundle source '{base_id}' (bounded scope; no global "
                "duplicate or replay protection exists)."
            )
        source_id = base_id
        if state == BOUNDED_DUPLICATE:
            ordinal = 2
            taken = existing_ids | {s["id"] for s in sources}
            while f"{base_id}.{ordinal}" in taken:
                ordinal += 1
            source_id = f"{base_id}.{ordinal}"
        elif base_id in existing_ids or any(
            s["id"] == base_id for s in sources
        ):
            raise InputError(
                f"source id {base_id!r} collides with a non-duplicate "
                "existing source"
            )
        sources.append(
            action_source(
                doc, state, explanation,
                validation_mode=mode, source_id=source_id,
            )
        )
        seen_digests.add(computed["action"])
        first_id_of.setdefault(computed["action"], base_id)

    if bundle is not None and args.out:
        bundle["sources"].extend(sources)
        bundle["sources"].sort(key=lambda source: str(source.get("id")))
        collection = bundle.setdefault("collection", {})
        if isinstance(collection, dict):
            added = sorted(source["id"] for source in sources)
            prior = collection.get("imported_sources")
            if isinstance(prior, list):
                added = sorted(set(prior) | set(added))
            collection["imported_sources"] = added
        _write_json(
            safe_output_path(args.out, workspace=workspace_boundary()), bundle
        )
        print(f"bundle: {args.out}")
    else:
        text = json.dumps(
            sources, indent=2, ensure_ascii=False, sort_keys=True
        ) + "\n"
        if args.out:
            out_path = safe_output_path(
                args.out, workspace=workspace_boundary()
            )
            if out_path.parent != Path(""):
                out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(text, encoding="utf-8", newline="\n")
            print(f"sources: {args.out}")
        else:
            sys.stdout.write(text)
    for source in sources:
        print(
            f"{source['id']}: {source['status']}", file=sys.stderr
        )
    return 0


def _cmd_bench_verify(args: argparse.Namespace) -> int:
    """Verify recorded benchmark cases; exit 1 when any check fails.

    Unverifiable checks never fail the run — they are disclosure. The
    harness runs no agent, applies no patch, and executes no command.
    """
    token = os.environ.get(args.token_env) if args.token_env else None
    api_url = (
        args.api_url or os.environ.get("GITHUB_API_URL") or DEFAULT_API_URL
    )
    reports = []
    for case_dir in args.case:
        reports.append(
            verify_case(
                Path(case_dir), live=args.live, token=token, api_url=api_url
            )
        )
    if args.json:
        payload: Any = reports[0] if len(reports) == 1 else reports
        text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True)
        sys.stdout.write(text + "\n")
    else:
        for report in reports:
            sys.stdout.write(render_bench_report(report))
    return 0 if all(report["ok"] for report in reports) else 1


def _check_context_integrity(bundle: Any, *, require_match: bool) -> None:
    """Zero-trust checks binding the bundle to its execution context.

    A committed context snapshot must match its own digest, and with
    ``--github-context-match`` the bundle subject must match the current
    GitHub context (resolved through the same code path the collector
    uses). Failures are operational errors (exit 2), never verdicts.
    """
    if isinstance(bundle, dict):
        collection = bundle.get("collection")
        if isinstance(collection, dict):
            has_snapshot = "context_snapshot" in collection
            has_digest = "context_digest" in collection
            if has_snapshot != has_digest:
                raise InputError(
                    "context snapshot binding is incomplete "
                    "(operational error, not a verdict)"
                )
            if has_snapshot and canonical.digest(
                collection.get("context_snapshot")
            ) != collection.get("context_digest"):
                raise InputError(
                    "context snapshot does not match its digest "
                    "(operational error, not a verdict)"
                )
            scope = collection.get(
                "observation_scope", collection.get("subject_context")
            )
            if scope is not None and not _scope_matches_subject(
                scope, bundle.get("subject")
            ):
                raise InputError(
                    "observation scope does not match bundle subject "
                    "(operational error, not a verdict)"
                )
    if not require_match:
        return
    context = resolve_github_context()
    subject = bundle.get("subject", {}) if isinstance(bundle, dict) else {}
    for key in ("repository", "sha"):
        expected = context.get(key)
        actual = subject.get(key)
        if expected != actual:
            raise InputError(
                f"bundle subject {key} {actual!r} does not match the "
                f"current GitHub context {expected!r} "
                "(operational error, not a verdict)"
            )


def _cmd_summarize(args: argparse.Namespace) -> int:
    record = _load_json(args.input)
    bindings: dict[str, str] | None = None
    if args.bundle or args.policy:
        bindings = verify_bindings(
            record if isinstance(record, dict) else {},
            bundle=_load_json(args.bundle) if args.bundle else None,
            policy_path=Path(args.policy) if args.policy else None,
        )
    if args.html:
        text, intact = render_html(record, bindings)
    else:
        text, intact = render_markdown(record)
    if bindings and any(value == "FAILED" for value in bindings.values()):
        intact = False
    if args.out:
        out_path = safe_output_path(args.out, workspace=workspace_boundary())
        if out_path.parent != Path(""):
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8", newline="\n")
        print(f"view: {args.out}")
    else:
        sys.stdout.write(text)
    return 0 if intact else 1


def _cmd_export(args: argparse.Namespace) -> int:
    record = _load_json(args.input)
    statement = build_statement(record)
    text = json.dumps(statement, indent=2, ensure_ascii=False, sort_keys=True)
    text += "\n"
    if args.out:
        out_path = safe_output_path(args.out, workspace=workspace_boundary())
        if out_path.parent != Path(""):
            out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text, encoding="utf-8", newline="\n")
        print(f"unsigned in-toto statement: {args.out}")
    else:
        sys.stdout.write(text)
    return 0



def _scope_matches_subject(scope: Any, subject: Any) -> bool:
    if not isinstance(scope, dict):
        return False
    identity = subject_identity(subject)
    if identity is None:
        return False
    repository = scope.get("repository")
    sha = scope.get("head_sha", scope.get("sha"))
    return (
        isinstance(repository, str)
        and isinstance(sha, str)
        and repository == identity.get("repository")
        and sha == identity.get("sha")
    )


def _bundle_bindings(
    record: dict[str, Any], bundle: Any,
) -> tuple[bool, str]:
    if not isinstance(bundle, dict):
        return False, "bundle is not an object"
    if (
        subject_identity(record.get("subject"))
        != subject_identity(bundle.get("subject"))
    ):
        return False, "record and bundle subjects differ"

    collection = bundle.get("collection")
    if not isinstance(collection, dict):
        return True, "not recorded in this bundle"

    has_snapshot = "context_snapshot" in collection
    has_digest = "context_digest" in collection
    if has_snapshot != has_digest:
        return False, "context snapshot binding is incomplete"
    if has_snapshot and canonical.digest(
        collection.get("context_snapshot")
    ) != collection.get("context_digest"):
        return False, "context snapshot digest does not recompute"

    scope = collection.get(
        "observation_scope", collection.get("subject_context")
    )
    if scope is None:
        return True, "not recorded in this bundle"
    if not _scope_matches_subject(scope, bundle.get("subject")):
        return False, "observation scope does not match bundle subject"
    return True, "exact repository and SHA match"


def _canonical_digest_string(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("sha256:")
        and len(value) == 71
        and all(ch in "0123456789abcdef" for ch in value[7:])
    )


def _cmd_verify(args: argparse.Namespace) -> int:
    record = _load_json(args.input)
    ok = verify_record(record)
    bundle: Any = None
    context_status = "not checked without a bundle"
    manifest_kind = "none"
    recorded: Any = None
    if ok and isinstance(record, dict):
        generator = record.get("generator")
        if isinstance(generator, dict):
            recorded = generator.get("verifier_manifest_digest")
            embedded = generator.get("verifier_manifest")
            if embedded is not None:
                if (
                    isinstance(embedded, dict)
                    and embedded.get("schema_version")
                    != "verifier-manifest-v0"
                ):
                    manifest_kind = "unsupported"
                    ok = _canonical_digest_string(recorded)
                else:
                    manifest_kind = "embedded"
                    ok = (
                        isinstance(embedded, dict)
                        and validate_verifier_manifest(embedded)
                        and recorded == embedded.get("manifest_digest")
                    )
            elif recorded is not None:
                manifest_kind = "digest-only"
                ok = _canonical_digest_string(recorded)

        observation = record.get("observation")
        if isinstance(observation, dict) and "observation_scope" in observation:
            ok = ok and _scope_matches_subject(
                observation["observation_scope"], record.get("subject")
            )

    if ok and args.bundle and isinstance(record, dict):
        bundle = _load_json(args.bundle)
        ok = record.get("input_bundle_digest") == canonical.digest(bundle)
        if ok:
            ok, context_status = _bundle_bindings(record, bundle)

    print("OK" if ok else "TAMPERED")
    if not ok or not isinstance(record, dict):
        return 1

    # A different valid verifier is disclosure, not record tampering.
    if _canonical_digest_string(recorded):
        current = verifier_manifest_digest()
        if manifest_kind == "embedded":
            if recorded == current:
                print("verifier: same manifest as this installation")
            else:
                print(
                    "verifier: valid embedded DIFFERENT manifest - "
                    "the record was "
                    f"produced by {recorded[:23]}..., this installation "
                    f"is {current[:23]}... (content address only; no "
                    "signing or authorship claim)"
                )
        elif manifest_kind == "unsupported":
            print(
                "verifier: embedded manifest schema is newer or unknown; "
                "record digest replay remains valid, file inventory was "
                "not interpreted"
            )
        else:
            if recorded == current:
                comparison = "same digest as this installation"
            else:
                comparison = "different digest from this installation"
            print(
                "verifier: digest-only record; file inventory is absent; "
                f"{comparison}"
            )
    else:
        print(
            "verifier: record predates manifest binding "
            "(digest replay remains valid)"
        )

    if isinstance(bundle, dict):
        print("subject binding: record and bundle match")
        print(f"subject context: {context_status}")
    return 0


def _load_json(path: str) -> Any:
    try:
        text = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {path}: {exc}") from exc
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise InputError(f"{path}: invalid JSON: {exc}") from exc
