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
from importlib import resources
from pathlib import Path
from typing import Any

from . import canonical
from .adapters import sarif_source, scorecard_source
from .checkpr import (
    counterfactual_blockers,
    fetch_branch_rules,
    fetch_commit_statuses,
    fetch_pr,
    parse_pr_url,
    pending_required,
    required_checks_from_rules,
    rules_digest,
    rules_summary_source,
    status_sources,
    strict_policy_from_rules,
)
from .collect import (
    DEFAULT_API_URL,
    Budget,
    build_bundle,
    build_generated_policy,
    github_context_snapshot,
    resolve_github_context,
    wait_for_required,
)
from .errors import InputError
from .evaluate import BLOCK, evaluate
from .evidence import build_record, verify_record
from .export import build_statement
from .paths import safe_output_path, workspace_boundary
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
        if args.command == "run":
            return _cmd_run(args)
        if args.command == "check-pr":
            return _cmd_check_pr(args)
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
        help="poll until required checks complete (default 0)",
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
        "api_calls": budget.api_calls,
        "waited_seconds": round(waited, 1),
    }
    if args.github_context:
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
        runs, truncated, incomplete, waited = wait_for_required(
            repository, sha, args.require,
            token=token, api_url=api_url,
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
            "api_calls": budget.api_calls,
            "waited_seconds": round(waited, 1),
        }
        if incomplete:
            collection["incomplete_required"] = incomplete
        if args.github_context:
            snapshot = github_context_snapshot()
            collection["context_snapshot"] = snapshot
            collection["context_digest"] = canonical.digest(snapshot)
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
        _write_json(safe_output_path(args.bundle_out, workspace=workspace), bundle)

    if args.policy:
        policy_path = Path(args.policy)
    elif args.policy_pack:
        policy_path = resolve_policy_pack(args.policy_pack)
    elif not args.input:
        generated = build_generated_policy(bundle, required=args.require)
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
    rules = fetch_branch_rules(
        coords["api_url"], coords["slug"], pr["base_ref"],
        token=token, budget=budget,
    )
    controls = required_checks_from_rules(rules)
    required_ids = [control["context"] for control in controls]

    runs, truncated, incomplete, waited = wait_for_required(
        coords["repository"], pr["head_sha"], required_ids,
        token=token, api_url=coords["api_url"],
        wait_seconds=args.wait_seconds, poll_interval=args.poll_interval,
        budget=budget,
    )
    statuses = fetch_commit_statuses(
        coords["api_url"], coords["slug"], pr["head_sha"],
        token=token, budget=budget,
    )
    run_names = {
        run.get("name") for run in runs if isinstance(run.get("name"), str)
    }
    status_srcs, skipped_contexts = status_sources(
        statuses, exclude_contexts={str(n) for n in run_names}
    )
    still_running = pending_required(runs, status_srcs, required_ids)
    status = "complete"
    if truncated:
        status = "truncated"
    elif incomplete:
        status = "wait_timeout"
    collection: dict[str, Any] = {
        "status": status,
        "api_calls": budget.api_calls,
        "waited_seconds": round(waited, 1),
        "rules_digest": rules_digest(rules),
        "required_controls": controls,
        "strict_up_to_date_required": strict_policy_from_rules(rules),
        "pr": {
            "state": pr["state"],
            "merged": pr["merged"],
            "draft": pr["draft"],
            "from_fork": pr["from_fork"],
        },
    }
    if incomplete:
        collection["incomplete_required"] = incomplete
    if still_running:
        collection["pending_required"] = still_running
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
        bundle, required=required_ids, allow_missing_required=True
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
        f"enforced by active branch rules on '{pr['base_ref']}'."
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
    if still_running:
        print(
            "Still running (fails closed as missing until finished; use "
            "--wait-seconds): " + ", ".join(still_running)
        )
    if would_block:
        print(
            "Counterfactual: would BLOCK if required: "
            + ", ".join(would_block)
        )
    print(
        "Note: this check is a read-only observer of status-check rules; "
        "reviews and other rule types are summarized in 'branch.rules' "
        "but not evaluated, and rule bypass actors are not observable "
        "from the public API."
    )
    print()
    text, _ = render_markdown(record)
    sys.stdout.write(text)
    if enforce and decision.verdict == BLOCK:
        return 1
    return 0


def _check_context_integrity(bundle: Any, *, require_match: bool) -> None:
    """Zero-trust checks binding the bundle to its execution context.

    A committed context snapshot must match its own digest, and with
    ``--github-context-match`` the bundle subject must match the current
    GitHub context (resolved through the same code path the collector
    uses). Failures are operational errors (exit 2), never verdicts.
    """
    if isinstance(bundle, dict):
        collection = bundle.get("collection")
        if isinstance(collection, dict) and "context_snapshot" in collection:
            snapshot = collection.get("context_snapshot")
            claimed = collection.get("context_digest")
            if canonical.digest(snapshot) != claimed:
                raise InputError(
                    "context snapshot does not match its digest "
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
    text, intact = render_markdown(record)
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
