from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

README_LOCAL_HYGIENE_BLOCK = """Run the local hygiene checks with:

```bash
python -m ruff check .
python -m mypy
python -m pytest
python tools/check_public_surface.py
```"""

REQUIRED_SNIPPETS = {
    "README.md": [
        "Phase 2: the local `evaluate` CLI and the advisory GitHub Action "
        "are implemented.",
        "GitHub can show green even when no check is required",
        "Not another AI reviewer",
        "## First value in one PR",
        "What AOS found:",
        "docs/assets/aos-warn-evidence.png",
        "Phase 3 has started: the zero-config GitHub check-runs collector "
        "is implemented",
        "UNSIGNED_NOT_OFFICIAL",
        "No production, compliance, signing, SLSA, or security-audit claim",
        README_LOCAL_HYGIENE_BLOCK,
        "```bash\npython tools/check_public_surface.py\n```",
        "Apache-2.0. See [LICENSE](LICENSE).",
        "See [NOTICE](NOTICE).",
        "checks: read",
        "actions: read",
        "pull-requests: read",
        "statuses: read",
        "Self-Test Mode",
        "No checkout is needed",
        "docs/RELEASE_GOVERNANCE.md",
        "docs/STANDARDS_COMPATIBILITY.md",
        "docs/TRUST.md",
        "docs/BUYER_FAQ.md",
        "docs/GUIDED_PILOT.md",
        "Pre-pilot validation",
        "## External availability",
        "FREE_SELF_SERVE_VALIDATION",
        "collects no\ntelemetry",
        "benchmarks/value/ASSESSMENT.md",
        ".github/workflows/aos-workflow-gate-self.yml",
    ],
    "docs/VALUE.md": [
        "Measured, not promised",
        "What this does not promise",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/ONE_PAGER.md": [
        "free self-serve advisory validation is open",
        "Find merge-control gaps that a green GitHub view can miss",
        "Immediate developer value",
        "external utility and market value remain unvalidated",
        "## Technical proof",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/PUBLISHED_VERSION": ["0.36.0"],
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
        "GitHub can show green when no check is required",
        "Not another AI reviewer",
        "Useful in daily work",
        "free advisory\npreview",
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
        "No human is required to install or evaluate",
        "## Where a human is required",
        "no\naccount, trial clock, or telemetry",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/COMPARISON.md": [
        "**not a ranking**",
        "different tools answer different\nquestions",
        "## Complementary by design",
        "no competitor tool was benchmarked or scored",
        "no superiority, security, or compliance claim",
    ],
    "docs/VALUE_METRICS.md": [
        "counted, not estimated",
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
        "the operator's\nclaim, not the gate's",
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
    "docs/SCOPE.md": [
        "## Decision boundary",
        "UNSIGNED_NOT_OFFICIAL",
        "It does not mean the underlying source signals are complete",
    ],
    "docs/ADOPTION_GUIDE.md": [
        "## Competency unblock",
        "## Barriers and design responses",
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
        "in-toto attestations",
        "OpenSSF Scorecard",
        "not a compliance claim",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/RELEASE_GOVERNANCE.md": [
        "AOS Workflow Gate CI / validate",
        "no Lean build is required",
        "Do not delete, recreate, or force-push a published `v*` tag",
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
        "## Phase 0: public bootstrap",
        "## Phase 1: local MVP CLI",
        "## Phase 2: GitHub Action advisory mode",
        "## Phase 3: signal adapters and policy packs",
        "## MVP scope lock (v0.22)",
        "no new commands, contracts, or integrations",
        "technically self-contained",
        "These are future layers, not current claims.",
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


def fail(message: str) -> None:
    print(f"public-surface check failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def check_docs_index() -> None:
    data = json.loads(read_text("docs.json"))
    for section in INDEX_SECTIONS:
        for item in data.get(section, []):
            if not (ROOT / item).exists():
                fail(f"docs.json references missing {section} path: {item}")


def check_required_snippets() -> None:
    for path, snippets in REQUIRED_SNIPPETS.items():
        text = read_text(path)
        for snippet in snippets:
            if snippet not in text:
                fail(f"{path} is missing required snippet: {snippet!r}")


def check_claim_boundary() -> None:
    checked_paths = list(CLAIM_SCAN_EXTRA_PATHS)
    data = json.loads(read_text("docs.json"))
    for section in ("documents", "examples", "policies"):
        checked_paths.extend(data.get(section, []))

    for path in checked_paths:
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

    pyproject = read_text("pyproject.toml")
    for snippet in (
        "mypy>=1.10,<2",
        "pytest>=8.2,<10",
        "ruff>=0.6,<1",
        "disallow_untyped_defs = true",
    ):
        if snippet not in pyproject:
            fail(f"pyproject.toml is missing required hygiene snippet: {snippet!r}")

    workflow = read_text(".github/workflows/aos-workflow-gate-ci.yml")
    required_workflow_snippets = (
        "name: AOS Workflow Gate CI",
        "name: AOS Workflow Gate CI / validate",
        "uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd",
        "persist-credentials: false",
        "uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1",
        "python -m pip install -e .[dev]",
        "python -m ruff check .",
        "python -m mypy",
        "python -m pytest",
        "python tools/check_public_surface.py",
        "yaml.safe_load(open('action.yml'))",
    )
    for snippet in required_workflow_snippets:
        if snippet not in workflow:
            fail(f"workflow is missing required hygiene snippet: {snippet!r}")

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
        fail(
            "version.py and docs/PUBLISHED_VERSION must use X.Y.Z"
        )
        return
    candidate_key = tuple(int(part) for part in candidate_match.groups())
    published_key = tuple(int(part) for part in published_match.groups())
    if published_key > candidate_key:
        fail(
            "published version cannot be newer than the package candidate"
        )

    expected = f"aos-workflow-gate@v{published_version}"
    data = json.loads(read_text("docs.json"))
    documents = [
        "README.md",
        ".github/ISSUE_TEMPLATE/feedback.yml",
        *data.get("documents", []),
    ]
    for path in documents:
        text = read_text(path)
        for match in re.finditer(
            r"aos-workflow-gate@v[0-9][^\s\"'`)\\<]*", text
        ):
            if match.group(0) != expected:
                fail(
                    f"{path} references stale version {match.group(0)!r}; "
                    f"published is {expected!r}"
                )


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
    check_docs_index()
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
