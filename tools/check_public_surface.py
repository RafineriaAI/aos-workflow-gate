from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import NoReturn
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

_BRANCH_LEAKING_MERGE_RE = re.compile(
    r"^(?:Merge pull request #\d+ from \S+|"
    r"Merge (?:remote-tracking )?branch ['\"]\S+['\"])",
    re.MULTILINE,
)

README_LOCAL_HYGIENE_BLOCK = """Run the local hygiene checks with:

```bash
python -m ruff check .
python -m mypy
python -m pytest
python tools/check_public_surface.py
```"""

REQUIRED_SNIPPETS = {
    "README.md": [
        "Check your project before you share it. No Git or test expertise required.",
        "aos-check",
        "AOS could not find a runnable behavioral test",
        "The GitHub gate verifies controls, not code.",
        (
            "control that is missing, stale, produced by the\n"
            "wrong app, or modified by the same PR"
        ),
        (
            "Exact commit · Default Action read-only · Advisory by default · "
            "No source-code upload"
        ),
        "docs/assets/readme-contrast.png",
        "docs/assets/readme-contrast-mobile.png",
        "scramble-robot/questix#99",
        "## Try it on any public PR",
        "## What AOS catches",
        "Not another AI reviewer",
        "## First value in one PR",
        "No checkout, manual policy, bundle, or `required-checks` list",
        "## A decision you can act on",
        "The verdict and the process exit code are separate.",
        "## Who it is for",
        "Best fit: teams with multiple repositories",
        "## Evidence and replay",
        "docs/assets/aos-warn-evidence.png",
        "## Trust boundary",
        "No LLM participates in the verdict path.",
        "UNSIGNED_NOT_OFFICIAL",
        "Mechanism verification and market validation are separate.",
        "Daily usefulness, alert precision in\nexternal teams",
        "`NO_GO`",
        "FREE_SELF_SERVE_VALIDATION",
        "There is no active paid offering.",
        README_LOCAL_HYGIENE_BLOCK,
        "```bash\npython tools/check_public_surface.py\n```",
        "Apache-2.0. See [LICENSE](LICENSE).",
        "See [NOTICE](NOTICE).",
        "checks: read",
        "actions: read",
        "pull-requests: read",
        "statuses: read",
        "No telemetry or account is required.",
        "docs/RELEASE_GOVERNANCE.md",
        "docs/STANDARDS_COMPATIBILITY.md",
        "docs/VALUE.md",
        "docs/BUYER_FAQ.md",
        "docs/COMPARISON.md",
        "docs/TRUST.md",
        "docs/SECURITY_READINESS.md",
        "benchmarks/value/ASSESSMENT.md",
        ".github/workflows/aos-workflow-gate-self.yml",
    ],
    "action.yml": [
        "Pre-merge control assurance for the exact PR commit.",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "pyproject.toml": [
        "Local code verification and deterministic workflow decisions.",
    ],

    "docs/VALUE.md": [
        "low-frequency, potentially high-cost",
        "## Best-fit user and buyer",
        "## Commercial packaging hypothesis",
        "actionable rate and alert acceptance rate",
        "Measured, not promised",
        "What this does not promise",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/ONE_PAGER.md": [
        "free self-serve advisory validation is open",
        (
            "control that is missing, stale, produced by the wrong app, "
            "or\nmodified by the same PR"
        ),
        "pre-merge control assurance",
        "Not the primary paid use case",
        "Policy packs alone are too copyable",
        "external utility and market value remain unvalidated",
        "## Technical proof",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/PUBLISHED_VERSION": ["0.37.1"],
    "docs/GUIDED_PILOT.md": [
        "Status: intake closed",
        "## Future design-partner variant",
        "mutual NDA before any non-public material",
        "does not deliver a security audit",
    ],
    ".github/ISSUE_TEMPLATE/feedback.yml": [
        "Exact AOS version tested",
        "What did AOS add beyond the existing CI or review?",
        "Would you keep the advisory Action enabled?",
        "May this response be used as product-research evidence?",
        "include code, secrets, logs, or other confidential material",
    ],
    "docs/MARKETPLACE_LISTING.md": [
        "UI-only",
        "UNSIGNED_NOT_OFFICIAL",
        "Status:",
    ],
    "docs/index.html": [
        "without cookies, analytics,\nor network calls",
        "UNSIGNED_NOT_OFFICIAL",
        "no\nproduction, compliance, or security-audit claim",
        (
            "control that is missing, stale,\nproduced by the wrong app, "
            "or modified by the same PR"
        ),
        "AOS verifies the gate, not the code.",
        "Not another AI reviewer",
        "Who it is for",
        "free advisory preview with no\nactive paid offering",
        'name="description"',
        'property="og:image"',
    ],
    "benchmarks/value/README.md": [
        "product-evidence claim gate",
        "## Current result",
        "`NO_GO`",
        "Mechanism evidence: `MECHANISM_CONFIRMED`",
        "Signal validity: `SIGNAL_INCONCLUSIVE`",
        "Internal product test: `PRODUCT_TEST_READY`",
        "Practical-utility testability: `UTILITY_TEST_READY`",
        "External-test readiness: `READY_FOR_EXTERNAL_VALIDATION`",
        "Participant access: `RECRUITMENT_PENDING`",
        "Validation distribution: `FREE_SELF_SERVE_VALIDATION`",
        "External participants: currently unavailable",
        "Internal tests establish only",
        "## Advancement rule",
        "Formative usability requires 8-12\nindependent developers",
        "versioned comparative-study contract",
        "bounded discovery sample, not a market study",
        "free self-serve channel is open",
    ],
    "benchmarks/value/ASSESSMENT.md": [
        "**Product-claim status: `NO_GO`**",
        "Cases: **100** across **10** repositories",
        "Mechanism evidence: `MECHANISM_CONFIRMED`",
        "GitHub `clean` plus AOS `WARN/non_independent_evidence`",
        "Exact-baseline actionable findings",
        "Practical-utility testability: `UTILITY_TEST_READY`",
        "External-test readiness: `READY_FOR_EXTERNAL_VALIDATION`",
        "Participant access: `RECRUITMENT_PENDING`",
        "Validation distribution: `FREE_SELF_SERVE_VALIDATION`",
        "External participants currently available: **no**",
        "Free self-serve validation available: **yes**",
        "`FREE_SELF_SERVE_VALIDATION` permits a public, no-cost advisory",
        "`NO_GO` blocks efficacy or value claims",
    ],
    "benchmarks/value/HYBRID_PROTOCOL.md": [
        "free self-serve validation available; qualified recruitment pending",
        "No external developers or teams are currently enrolled",
        "FREE_SELF_SERVE_VALIDATION",
        "MECHANISM_CONFIRMED",
        "UTILITY_TEST_READY",
        "READY_FOR_EXTERNAL_VALIDATION",
        "RECRUITMENT_PENDING",
        "Automated tests, maintainers, and AI",
        "8-12 independent developers",
        "5-10 independent teams",
        "versioned\nobservation and analysis contract",
        "`NO_GO`",
    ],
    "benchmarks/value/utility-task-corpus.json": [
        '"schema_version": "utility-task-corpus-v0"',
        '"case_id": "github-green-self-validating"',
        '"classification": "positive_control"',
        '"classification": "negative_control"',
    ],
    "benchmarks/value/utility-test-readiness.json": [
        '"schema_version": "utility-test-readiness-v0"',
        "Internal red-team evidence only",
        '"case_count": 8',
        '"positive_controls": 2',
        '"negative_controls": 6',
        '"access": "free"',
        '"channel": "public_self_serve"',
        '"mode": "advisory"',
        '"telemetry": "none"',
    ],
    "benchmarks/value/EXACT_CONTRAST.md": [
        "Three prospective, read-only cases across three public repositories",
        "AOS WARN: non_independent_evidence",
        "What this proves",
        "What this does not prove",
        "technical semantic\nadvantage, not product-publication readiness",
    ],
    "docs/PILOT_PACKAGE.md": [
        "Status: intake closed",
        "file by file",
        "can replay without us",
        "## Handover checklist",
        "nothing\n      is retained on our side",
        "not a security audit",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/templates/PILOT_REPORT_TEMPLATE.md": [
        "counted, not estimated",
        "everything keeps working\nwithout RafineriaAI",
        "makes no security-audit, compliance, or ROI claim",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/FUNNEL.md": [
        "free self-serve advisory validation is open",
        "No RafineriaAI human is required to install or evaluate",
        "## Where a human is required",
        "## Commercialization gate",
        "Policy packs alone are not treated as a sufficient paid moat",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/COMPARISON.md": [
        "**not a ranking**",
        "## Category boundary",
        "pre-merge control assurance",
        "## Differentiating bundle",
        "no\ncompetitor tool was benchmarked or scored",
        "no superiority,\nsecurity, compliance, market-demand, or ROI claim",
    ],
    "docs/VALUE_METRICS.md": [
        "counted, not estimated",
        "## Required external field metrics",
        "Actionable rate",
        "Decision-change rate",
        "30-day retention",
        "## What we deliberately do not compute",
        "No return-on-investment figure",
        "will not invent",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/case-studies/zero-required-checks.md": [
        "GitHub\nrequired one status check and permitted the merge",
        "Scope is required status checks, not full merge-readiness",
        "Current zero-config collection instead discovers active\n"
        "GitHub branch requirements",
        "The only alert is the decision gap itself",
        "remain visible in the evidence table",
        "not a vulnerability, product\nutility",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/case-studies/green-but-incomplete.md": [
        "skipped **by design**",
        "shows visibility, not a vulnerability",
        "makes no security claim",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/USER_FAQ.md": [
        "## Failure taxonomy",
        "## Exit codes by command",
        "Never treat it as a policy decision",
        "aos-workflow-gate verify --input gate-decision.json",
        "wait-for-checks",
    ],
    "docs/PREFLIGHT.md": [
        "No permission is assumed without probing",
        "Preflight produces **no verdict**",
        "## Diagnostic code registry",
        "a code never changes meaning across versions",
        "AOS-PERM-003",
        "## Exit codes",
        "Degraded",
        "## Automatic preflight in collection",
        "**no duplicate API call**",
        "`can_continue: no`",
        "`can_continue: yes`",
        "failing closed, never silently missing",
    ],
    "docs/SECURITY_READINESS.md": [
        "## Private-repo data model",
        "no security-audit claim is made",
        "Never code, diffs, logs, or annotations",
        "control characters",
        "AOS_GATE_WORKSPACE",
        "writes only within the workspace",
        "30-second",
        "fails closed",
        "## Zero-trust signalling",
        "App-bound requirement identity",
        "Verifier artifact binding",
        "verifier substitution\n  is detectable, never silent",
        "digest replay is forever",
        "deliberately not full merge-readiness",
        "Strict token demarcation",
        "Permissions contract",
        "zero-trust signalling adds no signing, no provenance",
        "## Operational resilience",
        "Infrastructure failure is never a policy verdict",
        "Collection status is evidence",
        "`can_block` in the record",
        "truncation can never turn a BLOCK into a\n  PASS",
        "No checkout required",
    ],
    "docs/TRUST.md": [
        "Read-only by design",
        "no telemetry",
        "Zero runtime dependencies",
        "AOS Verdict Seal",
        "reserved product designation",
        "no signing\nservice exists yet",
    ],
    "docs/BUYER_FAQ.md": [
        "What data leaves my environment?",
        "No write scopes",
        "Apache-2.0",
        "It is not a security audit",
        "AOS Verdict Seal",
        "active paid offering",
    ],
    "docs/ADAPTERS.md": [
        "mechanical, never judgmental",
        "Interpretation stays in the\npolicy",
        "not as a verdict",
        "do not verify the authenticity",
        "no plugin runtime",
        "a\nsource can never mark itself required",
    ],
    "benchmarks/README.md": [
        "## Automated contrast and the adversarial corpus",
        "never an input to the evaluator",
        "asserts byte equality",
        "no staged repositories, no\nfabricated signals, no synthetic scenarios",
        "## Dogfooding boundary",
        "Claude Code\n(Anthropic), operated by the maintainer",
        "Nothing here generalizes beyond this\nrepository",
        "controlled counterfactual on real history",
        "required-evidence gap",
        "advisory-visibility gap",
        "operator-declared",
        "retrospective real-history benchmark",
        "counted, not estimated",
        "a sample, not a study",
        "ranks no\ntools and scores no competitors",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/BENCHMARK_HARNESS.md": [
        "**it runs nothing**",
        "predeclared",
        "written before the run, not after the fact",
        "## Checks and the verified vs unverifiable boundary",
        "no patch-authorship claim",
        "no cryptographic\n  authorship claim",
        "no arbitrary command execution",
        "does not mean the agent's change was\ngood, safe, or approved",
    ],
    "docs/AGENT_ACTION.md": [
        "evidence a policy can require, never an approval",
        "## Validation states",
        "integrity, then binding, then\nfreshness failure, then duplication, "
        "then unknown freshness",
        "No execution authority",
        "No semantic approval claim",
        "No global duplicate or replay protection",
        "`freshness_unverified`",
        "nothing is silently assumed fresh",
        "cross-repository and fork flows are out of scope",
        "policy decides what any state means",
    ],
    "docs/SOURCE_CONTRACT.md": [
        "no plugin runtime",
        "Adapter-defined, non-enum",
        "an observation, never a verdict",
        "no `required` field",
        "policy-owned",
        "### Identity-completeness invariant",
        "### Normative canonicalization",
        "golden digest vectors",
        "recomputes the digest and verifies it",
        "one shared validation path",
        "A signal must not be able to\npromote itself",
        "historical records are never rewritten",
        "not authenticity",
    ],
    "docs/POLICY_PACKS.md": [
        "copy one, rename the `policy_id`",
        "packs encode structure, not judgment",
        "mode: blocking",
    ],
    "docs/CI_INTEGRATIONS.md": [
        "platform-neutral",
        "GitHub Enterprise Server",
        "GitLab jobs collector is planned",
        "collection provenance and completeness on those platforms remain "
        "the\noperator's claim, not the gate's",
        "checks: read",
        "actions: read",
        "pull-requests: read",
        "statuses: read",
        "read-only by design",
    ],
    "docs/DECISION_PREDICATE.md": [
        "https://github.com/RafineriaAI/aos-workflow-gate/decision-record/v0",
        "https://in-toto.io/Statement/v1",
        "UNSIGNED",
        "not an official RafineriaAI/AOS verdict",
        "must not be called an attestation",
    ],
    "NOTICE": [
        "Copyright (c) 2026 Szymon Hetnar (RafineriaAI)",
        "does not grant any right to use",
        "Apache-2.0, Section 6",
        "UNSIGNED_NOT_OFFICIAL",
        '"AOS Verdict Seal" is a reserved product designation',
        "no right to\nuse that designation is granted",
    ],
    "docs/ARCHITECTURE.md": [
        "standalone Python package with zero runtime",
        "does not prove this package's source-status rules",
        "kernel-backed claim requires an explicit shared contract",
    ],

    "docs/SCOPE.md": [
        "pre-merge control assurance",
        "No active paid product",
        "Full merge-readiness",
        "## Decision boundary",
        "UNSIGNED_NOT_OFFICIAL",
        "It does not mean the underlying source signals are complete",
        "No artifact produced here is kernel-generated or kernel-verified",
    ],
    "docs/ADOPTION_GUIDE.md": [
        "AOS verifies the gate, not the code",
        "## Competency unblock",
        "## Barriers and design responses",
        "Correct alerts may still lack business importance",
        "Individual developers may not need another paid tool",
        "## Research inputs",
    ],
    "docs/STANDARDS_COMPATIBILITY.md": [
        "## Compatibility principles",
        "## Integration map",
        "## Market-entry effect",
        "SLSA",
        "SPDX",
        "CycloneDX",
        "SARIF 2.1.0",
        "in-toto Statement v1",
        "OpenSSF Scorecard",
        "not a compliance claim",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/RELEASE_GOVERNANCE.md": [
        "AOS Workflow Gate CI / validate",
        "no Lean build is required",
        "does not prove this repository's\nworkflow evaluator",
        "A future kernel-backed claim requires a versioned shared contract",
        "standalone workflow gate, not a kernel proof or kernel-backed verdict",
        "Do not delete, recreate, or force-push a published `v*` tag",
        "## Public Merge Metadata",
        "--subject \"<public outcome>\"",
        "tools/check_public_surface.py --check-head-commit",
        (
            "no production, compliance, security-audit, signing, SBOM, SLSA, "
            "or attestation claim"
        ),
        "## Phase 2 Release Boundary",
        "Advisory mode must stay the default",
        "## Self-Gated Releases",
        "A failed release gate means the GitHub Release must\nnot be published",
        "attached to the GitHub Release as assets",
    ],
    "ROADMAP.md": [
        "## Current status",
        "## Completed foundations",
        "### Phase 1: local deterministic gate",
        "### Phase 2: advisory GitHub Action",
        "## Stable surface and product experiments",
        "## Next milestone: external value validation",
        "No dashboard, SaaS layer, broad adapter catalog, or release claim",
        "technically correct mechanism is not sufficient evidence",
        "## Deferred",
    ],
    "CONTRIBUTING.md": [
        "## First setup",
        'python -m pip install -e ".[dev]"',
        "## Change workflow",
        "## Review requirements",
        "existing committed records and benchmark cases still replay",
    ],
    "docs/DEVELOPMENT.md": [
        "canonical maintainer onboarding guide",
        "## Repository map",
        "## Non-negotiable invariants",
        "## Documentation ownership",
        "## Ownership and decisions",
        "## Release handoff",
    ],
    "SECURITY.md": [
        "latest immutable GitHub release",
        "free public advisory preview",
        "GitHub private\nvulnerability reporting",
        "## Data and permission boundary",
        "UNSIGNED_NOT_OFFICIAL",
    ],
}

UNSUPPORTED_POSITIVE_CLAIMS = [
    re.compile(r"\bis production-ready\b", re.IGNORECASE),
    re.compile(r"\bproduction-grade\b", re.IGNORECASE),
    re.compile(r"\bzero-risk\b", re.IGNORECASE),
    re.compile(r"\brisk-free\b", re.IGNORECASE),
    re.compile(r"\bsuperior to\b", re.IGNORECASE),
    re.compile(r"\boutperforms?\b", re.IGNORECASE),
    re.compile(r"\bprovides compliance certification\b", re.IGNORECASE),
    re.compile(r"\bcertifies compliance\b", re.IGNORECASE),
    re.compile(r"\bproves (?:the )?repository is secure\b", re.IGNORECASE),
    re.compile(r"\bformally proves workflow correctness\b", re.IGNORECASE),
]

CLAIM_SCAN_EXTRA_PATHS = ["action.yml", "SECURITY.md"]

INDEX_SECTIONS = (
    "documents", "examples", "policies", "benchmarks", "tools", "ci", "assets",
)
MARKDOWN_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
HTML_LINK_RE = re.compile(r"""(?:href|src)=["']([^"']+)["']""", re.IGNORECASE)
SHELL_FENCE_RE = re.compile(
    r"\`\`\`(?:bash|sh|shell|powershell)\s*\n(.*?)\`\`\`",
    re.IGNORECASE | re.DOTALL,
)
ACTION_USE_RE = re.compile(
    r"^\s*(?:-\s+)?uses:\s*(?:\./|"
    r"RafineriaAI/aos-workflow-gate@)",
)
EXTERNAL_LINK_PREFIXES = (
    "http://", "https://", "mailto:", "data:", "javascript:", "tel:",
)


def _relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def _files_under(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {
        _relative(item)
        for item in path.rglob("*")
        if item.is_file()
        and "__pycache__" not in item.parts
        and item.suffix not in {".pyc", ".pyo"}
    }


def _expected_index_paths() -> set[str]:
    expected = {
        "README.md",
        "CONTRIBUTING.md",
        "ROADMAP.md",
        "SECURITY.md",
        "LICENSE",
        "NOTICE",
        "action.yml",
        "pyproject.toml",
        ".editorconfig",
    }
    expected.update(_files_under(ROOT / "docs"))
    expected.update(_files_under(ROOT / "benchmarks"))
    expected.update(_files_under(ROOT / "examples"))
    expected.update(_files_under(ROOT / "policies"))
    expected.update(_files_under(ROOT / "aos_workflow_gate" / "packs"))
    expected.update(_files_under(ROOT / "tools"))
    expected.update(_files_under(ROOT / ".github"))
    expected.update(
        _relative(path)
        for path in (ROOT / "tests").glob("test_*.py")
        if path.is_file()
    )
    expected.update(_files_under(ROOT / "tests" / "data" / "historical"))
    return expected


def _indexed_paths(data: dict[str, object]) -> list[str]:
    paths: list[str] = []
    for section in INDEX_SECTIONS:
        values = data.get(section, [])
        if not isinstance(values, list):
            fail(f"docs.json section {section!r} must be a list")
        for item in values:
            if not isinstance(item, str):
                fail(f"docs.json section {section!r} contains a non-string path")
            paths.append(item)
    return paths


def _text_document_paths(data: dict[str, object]) -> list[str]:
    return sorted(
        path
        for path in _indexed_paths(data)
        if Path(path).suffix.lower() in {".md", ".html"}
    )


def _local_link_target(raw: str) -> str | None:
    target = raw.strip()
    if target.startswith("<") and ">" in target:
        target = target[1 : target.index(">")]
    else:
        target = target.split(maxsplit=1)[0]
    target = unquote(target)
    if not target or target.startswith(("#", *EXTERNAL_LINK_PREFIXES)):
        return None
    return target.split("#", 1)[0].split("?", 1)[0] or None


def check_local_links() -> None:
    data: dict[str, object] = json.loads(read_text("docs.json"))
    for relative_path in _text_document_paths(data):
        source = ROOT / relative_path
        text = source.read_text(encoding="utf-8")
        raw_targets = MARKDOWN_LINK_RE.findall(text)
        raw_targets.extend(HTML_LINK_RE.findall(text))
        for raw_target in raw_targets:
            target = _local_link_target(raw_target)
            if target is None:
                continue
            candidate = (
                ROOT / target.lstrip("/")
                if target.startswith("/")
                else source.parent / target
            ).resolve()
            root = ROOT.resolve()
            if candidate != root and root not in candidate.parents:
                fail(f"{relative_path} links outside the repository: {raw_target!r}")
            if not candidate.exists():
                fail(
                    f"{relative_path} references a missing local path: "
                    f"{raw_target!r}"
                )


def _command_options() -> dict[str, set[str]]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from aos_workflow_gate.cli import _build_parser

    parser = _build_parser()
    global_options = {
        option
        for action in parser._actions
        for option in action.option_strings
    }
    result: dict[str, set[str]] = {}
    for action in parser._actions:
        choices = getattr(action, "choices", None)
        if not isinstance(choices, dict):
            continue
        for name, subparser in choices.items():
            if not isinstance(name, str) or not isinstance(
                subparser, argparse.ArgumentParser
            ):
                continue
            result[name] = global_options | {
                option
                for sub_action in subparser._actions
                for option in sub_action.option_strings
            }
    return result


def _logical_shell_lines(block: str) -> list[str]:
    result: list[str] = []
    buffered = ""
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        continued = line.endswith(("\\", "`"))
        if continued:
            line = line[:-1].rstrip()
        buffered = f"{buffered} {line}".strip()
        if not continued:
            result.append(buffered)
            buffered = ""
    if buffered:
        result.append(buffered)
    return result


def check_cli_examples() -> None:
    options = _command_options()
    data: dict[str, object] = json.loads(read_text("docs.json"))
    for relative_path in _text_document_paths(data):
        if Path(relative_path).suffix.lower() != ".md":
            continue
        text = read_text(relative_path)
        for block in SHELL_FENCE_RE.findall(text):
            for line in _logical_shell_lines(block):
                for segment in line.split("|"):
                    match = re.search(r"(?:^|\s)(aos-workflow-gate\s+.+)", segment)
                    if match is None:
                        continue
                    try:
                        tokens = shlex.split(match.group(1), posix=True)
                    except ValueError as exc:
                        fail(f"{relative_path} has an invalid CLI example: {exc}")
                    if len(tokens) < 2:
                        fail(f"{relative_path} has a CLI example without a command")
                    command = tokens[1]
                    if command not in options:
                        fail(
                            f"{relative_path} uses unknown CLI command "
                            f"{command!r}"
                        )
                    for token in tokens[2:]:
                        if token == "--":
                            break
                        if not token.startswith("--"):
                            continue
                        option = token.split("=", 1)[0]
                        if option not in options[command]:
                            fail(
                                f"{relative_path} uses unknown {command} "
                                f"option {option!r}"
                            )


def check_action_examples() -> None:
    action = read_text("action.yml")
    try:
        input_block = action.split("\ninputs:\n", 1)[1].split(
            "\noutputs:\n", 1
        )[0]
    except IndexError:
        fail("action.yml must contain top-level inputs and outputs sections")
        return
    valid_inputs = set(
        re.findall(r"^  ([a-z][a-z0-9-]*):\s*$", input_block, re.MULTILINE)
    )
    data: dict[str, object] = json.loads(read_text("docs.json"))
    candidate_paths = set(_text_document_paths(data))
    candidate_paths.update(
        _relative(path)
        for path in (ROOT / ".github" / "workflows").glob("*.yml")
    )
    for relative_path in sorted(candidate_paths):
        lines = read_text(relative_path).splitlines()
        for index, line in enumerate(lines):
            if ACTION_USE_RE.search(line) is None:
                continue
            base_indent = len(line) - len(line.lstrip())
            with_indent: int | None = None
            for nested in lines[index + 1 :]:
                if not nested.strip() or nested.lstrip().startswith("#"):
                    continue
                indent = len(nested) - len(nested.lstrip())
                stripped = nested.strip()
                if with_indent is None:
                    if stripped == "with:" and indent >= base_indent:
                        with_indent = indent
                        continue
                    if indent <= base_indent:
                        break
                    continue
                if indent <= with_indent:
                    break
                match = re.match(r"([a-zA-Z0-9_-]+):", stripped)
                if match is not None and match.group(1) not in valid_inputs:
                    fail(
                        f"{relative_path} uses unknown Action input "
                        f"{match.group(1)!r}"
                    )


def fail(message: str) -> NoReturn:
    print(f"public-surface check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def merge_metadata_issues(message: str) -> list[str]:
    """Return public-hygiene violations in a merge commit message."""
    issues: list[str] = []
    if _BRANCH_LEAKING_MERGE_RE.search(message):
        issues.append("default merge subject exposes a branch")
    return issues


def check_head_commit_metadata() -> None:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%B"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    issues = merge_metadata_issues(result.stdout)
    if issues:
        fail(
            "HEAD commit metadata is not public-safe: "
            + "; ".join(issues)
        )


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_docs_index() -> None:
    data: dict[str, object] = json.loads(read_text("docs.json"))
    if data.get("status") != "public-advisory-preview":
        fail("docs.json status must match the current public advisory surface")

    paths = _indexed_paths(data)
    if len(paths) != len(set(paths)):
        duplicates = sorted(
            path for path in set(paths) if paths.count(path) > 1
        )
        fail(f"docs.json contains duplicate paths: {duplicates}")

    root = ROOT.resolve()
    for item in paths:
        resolved = (ROOT / item).resolve()
        if resolved != root and root not in resolved.parents:
            fail(f"docs.json path escapes the repository: {item}")
        if not resolved.exists():
            fail(f"docs.json references a missing path: {item}")

    missing = sorted(_expected_index_paths() - set(paths))
    if missing:
        fail(f"docs.json does not index public paths: {missing}")


def check_required_snippets() -> None:
    for path, snippets in REQUIRED_SNIPPETS.items():
        text = read_text(path)
        for snippet in snippets:
            if snippet not in text:
                fail(f"{path} is missing required snippet: {snippet!r}")


def check_claim_boundary() -> None:
    data: dict[str, object] = json.loads(read_text("docs.json"))
    checked_paths = set(CLAIM_SCAN_EXTRA_PATHS)
    checked_paths.update(_text_document_paths(data))
    for section in ("examples", "policies"):
        values = data.get(section, [])
        if isinstance(values, list):
            checked_paths.update(
                item for item in values if isinstance(item, str)
            )

    for path in sorted(checked_paths):
        text = read_text(path)
        for pattern in UNSUPPORTED_POSITIVE_CLAIMS:
            match = pattern.search(text)
            if match:
                fail(f"unsupported positive claim in {path}: {match.group(0)!r}")


def check_pilot_intake_closed() -> None:
    retired_paths = (
        ".github/ISSUE_TEMPLATE/guided-pilot-scoping.yml",
        "docs/pilot-wizard/index.html",
    )
    for path in retired_paths:
        if (ROOT / path).exists():
            fail(f"closed pilot intake surface still exists: {path}")

    active_link = "issues/new?template=guided-pilot-scoping.yml"
    data = json.loads(read_text("docs.json"))
    for path in ["action.yml", *data.get("documents", [])]:
        if active_link in read_text(path):
            fail(f"closed pilot intake link remains in {path}")


def check_examples() -> None:
    bundle = json.loads(read_text("examples/github-pr-signal-bundle.json"))
    if bundle.get("schema_version") != "draft-0":
        fail("example signal bundle must declare the current draft-0 input schema")
    if not bundle.get("subject", {}).get("sha"):
        fail("example signal bundle must include a subject sha")
    source_ids = [source.get("id") for source in bundle.get("sources", [])]
    if len(source_ids) != len(set(source_ids)):
        fail("example signal bundle contains duplicate source ids")

    policy = read_text("policies/default.yml")
    for snippet in (
        "schema_version: draft-0",
        "mode: advisory",
        "verification_status: UNSIGNED_NOT_OFFICIAL",
        "missing_required_source: BLOCK",
    ):
        if snippet not in policy:
            fail(f"draft policy is missing required snippet: {snippet!r}")


def check_decision_fixture() -> None:
    record = json.loads(read_text("examples/gate-decision.json"))
    required_keys = (
        "verdict",
        "verification_status",
        "record_digest",
        "input_bundle_digest",
        "can_block",
    )
    for key in required_keys:
        if key not in record:
            fail(f"committed decision fixture is missing '{key}'")
    if record.get("verification_status") != "UNSIGNED_NOT_OFFICIAL":
        fail("committed decision fixture must stay UNSIGNED_NOT_OFFICIAL")
    if record.get("verdict") not in {"PASS", "WARN", "BLOCK"}:
        fail("committed decision fixture verdict must be PASS, WARN, or BLOCK")


def check_repository_hygiene() -> None:
    license_text = read_text("LICENSE")
    if "Apache License" not in license_text or "Version 2.0" not in license_text:
        fail("LICENSE must remain Apache-2.0")

    pyproject_text = read_text("pyproject.toml")
    pyproject = tomllib.loads(pyproject_text)
    project = pyproject.get("project")
    if not isinstance(project, dict):
        fail("pyproject.toml must contain a project table")
    optional = project.get("optional-dependencies")
    if not isinstance(optional, dict):
        fail("pyproject.toml must contain optional dependencies")
    dev = optional.get("dev")
    if not isinstance(dev, list) or not all(
        isinstance(item, str) for item in dev
    ):
        fail("pyproject.toml dev extra must be a list of requirements")
    for package in ("mypy", "pytest", "ruff", "setuptools", "wheel"):
        if not any(
            re.fullmatch(
                rf"{re.escape(package)}(?:[<>=!~].*)?", requirement
            )
            for requirement in dev
        ):
            fail(f"pyproject.toml dev extra is missing {package!r}")
    if "disallow_untyped_defs = true" not in pyproject_text:
        fail("pyproject.toml must keep strict typed-definition checks")

    required_files = {
        ".editorconfig": ["charset = utf-8", "end_of_line = lf"],
        ".github/CODEOWNERS": [
            "* @RafineriaAI",
            "/aos_workflow_gate/ @RafineriaAI",
        ],
        ".github/pull_request_template.md": [
            "## Verification",
            "## Compatibility",
            "## Public Surface",
            "## Release Impact",
        ],
        "CONTRIBUTING.md": [
            "Python 3.11 or newer",
            'python -m pip install -e ".[dev]"',
            "docs/DEVELOPMENT.md",
        ],
    }
    for path, snippets in required_files.items():
        text = read_text(path)
        for snippet in snippets:
            if snippet not in text:
                fail(f"{path} is missing onboarding snippet: {snippet!r}")

    workflow = read_text(".github/workflows/aos-workflow-gate-ci.yml")
    required_workflow_snippets = (
        "name: AOS Workflow Gate CI",
        "name: AOS Workflow Gate CI / validate",
        "name: AOS Workflow Gate CI / Python 3.14",
        "uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd",
        "persist-credentials: false",
        "uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
        'python-version: "3.11"',
        'python-version: "3.14"',
        "python -m pip install -e .[dev]",
        "python -m ruff check .",
        "python -m mypy",
        "python -m pytest",
        "python tools/check_public_surface.py",
        "python tools/check_public_surface.py --check-head-commit",
        "yaml.safe_load(open('action.yml'))",
    )
    for snippet in required_workflow_snippets:
        if snippet not in workflow:
            fail(f"workflow is missing required hygiene snippet: {snippet!r}")
    if workflow.count("run: python -m pytest") < 2:
        fail("CI must run pytest on both supported-version boundary jobs")

    if (ROOT / ".github/workflows/public-surface.yml").exists():
        fail(
            "legacy public-surface workflow should be replaced by "
            "aos-workflow-gate-ci.yml"
        )

def check_permissions_contract() -> None:
    """The gate's workflows must never request a write scope."""
    workflow_dir = ROOT / ".github" / "workflows"
    for workflow_path in sorted(workflow_dir.glob("*.yml")):
        text = workflow_path.read_text(encoding="utf-8")
        match = re.search(r"^\s+[a-z-]+:\s*write\b", text, re.MULTILINE)
        if match:
            fail(
                f"{workflow_path.name} requests a write permission "
                f"({match.group(0).strip()!r}); the permissions contract "
                "is read-only"
            )


def check_version_consistency() -> None:
    version_match = re.search(
        r'__version__ = "([^"]+)"', read_text("aos_workflow_gate/version.py")
    )
    if version_match is None:
        fail("version.py does not define __version__")
        return
    version = version_match.group(1)

    if f'version = "{version}"' not in read_text("pyproject.toml"):
        fail(f"pyproject.toml version does not match version.py ({version})")

    published_version = read_text("docs/PUBLISHED_VERSION").strip()
    candidate_match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", version)
    published_match = re.fullmatch(
        r"(\d+)\.(\d+)\.(\d+)", published_version
    )
    if candidate_match is None or published_match is None:
        fail("version.py and docs/PUBLISHED_VERSION must use X.Y.Z")
        return
    candidate_key = tuple(int(part) for part in candidate_match.groups())
    published_key = tuple(int(part) for part in published_match.groups())
    if published_key > candidate_key:
        fail("published version cannot be newer than the package candidate")

    expected = f"aos-workflow-gate@v{published_version}"
    data: dict[str, object] = json.loads(read_text("docs.json"))
    documents = set(_text_document_paths(data))
    documents.add(".github/ISSUE_TEMPLATE/feedback.yml")
    for path in sorted(documents):
        text = read_text(path)
        for match in re.finditer(
            r"aos-workflow-gate@v[0-9][^\s\"'\`)\\<]*", text
        ):
            if match.group(0) != expected:
                fail(
                    f"{path} references stale version {match.group(0)!r}; "
                    f"published is {expected!r}"
                )

    roadmap_version = f"Current public release: `v{published_version}`."
    if roadmap_version not in read_text("ROADMAP.md"):
        fail("ROADMAP.md does not identify the current public release")

def check_action_surface() -> None:
    action = read_text("action.yml")
    required_action_snippets = (
        'using: "composite"',
        "UNSIGNED_NOT_OFFICIAL",
        'default: "false"',
        "GITHUB_STEP_SUMMARY",
        "args=(run --out",
        "python3 -m aos_workflow_gate summarize",
        "--policy-pack",
        "GATE_MODE: ${{ inputs.mode }}",
        "Keep the gate advisory until",
        "Self-Test Mode",
        "must not contain control characters",
        "AOS_GATE_WORKSPACE: ${{ github.workspace }}",
        "wait-for-checks",
        "automatic GitHub requirement discovery",
        "120-second stabilization window",
        "agent-review-advisory, evidence-integrity",
        "Reproduce locally",
        "Replay path:",
        "can-block=",
        "diagnosis=",
        "render_github_annotation",
        "clean(d['finding'])",
        "next-action=",
        "required-unverifiable=",
        ".aos-gate/evidence.html",
        "attach the files to a\n      release for permanence",
        "name: aos-gate-evidence",
        'include-hidden-files: "true"',
        "uses: actions/upload-artifact@"
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    )
    for snippet in required_action_snippets:
        if snippet not in action:
            fail(f"action.yml is missing required snippet: {snippet!r}")

    workflow = read_text(".github/workflows/aos-workflow-gate-self.yml")
    required_self_snippets = (
        "name: AOS Workflow Gate Self / advisory",
        "permissions:\n  contents: read\n  checks: read\n  actions: read\n"
        "  pull-requests: read\n  statuses: read",
        "persist-credentials: false",
        "uses: ./",
        "uses: actions/upload-artifact@"
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    )
    for snippet in required_self_snippets:
        if snippet not in workflow:
            fail(f"self-gate workflow is missing required snippet: {snippet!r}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check-head-commit",
        action="store_true",
        help="also reject branch-leaking metadata in the current commit",
    )
    args = parser.parse_args()

    if args.check_head_commit:
        check_head_commit_metadata()
        return

    check_docs_index()
    check_local_links()
    check_cli_examples()
    check_action_examples()
    check_required_snippets()
    check_claim_boundary()
    check_pilot_intake_closed()
    check_examples()
    check_decision_fixture()
    check_repository_hygiene()
    check_action_surface()
    check_permissions_contract()
    check_version_consistency()
    print("public-surface check OK")


if __name__ == "__main__":
    main()
