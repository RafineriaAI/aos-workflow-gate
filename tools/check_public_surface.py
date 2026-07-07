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
        "Phase 3 has started: the zero-config GitHub check-runs collector "
        "is implemented",
        "UNSIGNED_NOT_OFFICIAL",
        "No production, compliance, signing, SLSA, or security-audit claim",
        README_LOCAL_HYGIENE_BLOCK,
        "```bash\npython tools/check_public_surface.py\n```",
        "Apache-2.0. See [LICENSE](LICENSE).",
        "See [NOTICE](NOTICE).",
        "checks: read",
        "Self-Test Mode",
        "No checkout is needed",
        "docs/RELEASE_GOVERNANCE.md",
        "docs/STANDARDS_COMPATIBILITY.md",
        "docs/TRUST.md",
        "docs/BUYER_FAQ.md",
        "docs/GUIDED_PILOT.md",
        "issues/new?template=feedback.yml",
        "## Pilots and design partners",
        ".github/workflows/aos-workflow-gate-self.yml",
    ],
    "docs/VALUE.md": [
        "Measured, not promised",
        "What this does not promise",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/ONE_PAGER.md": [
        "deterministic evidence infrastructure for",
        "Proof, not promises",
        "commits neither side",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/GUIDED_PILOT.md": [
        "Submitting the form\n   commits neither side",
        "## Design Partner variant",
        "mutual NDA before any non-public material",
        "does not deliver a security audit",
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
        "deterministic evidence infrastructure for AI-controlled",
        'name="description"',
        'property="og:image"',
    ],
    "docs/pilot-wizard/index.html": [
        "Runs entirely in your browser",
        "No cookies, no\nanalytics, no network calls",
        "UNSIGNED_NOT_OFFICIAL",
        "commits neither side",
        "guided-pilot-scoping.yml",
        "aos-self-test.yml",
        "Copy workflow",
    ],
    "docs/PILOT_PACKAGE.md": [
        "file by file",
        "can replay\nwithout us",
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
        "human enters exactly once",
        "## Where a human is required",
        "no telemetry reporting you were ever here",
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
    "docs/case-studies/green-but-incomplete.md": [
        "skipped **by design**",
        "shows visibility, not a vulnerability",
        "makes no security claim",
        "UNSIGNED_NOT_OFFICIAL",
    ],
    "docs/USER_FAQ.md": [
        "## Failure taxonomy",
        "Never treat it as a policy decision",
        "aos-workflow-gate verify --input gate-decision.json",
        "wait-for-checks",
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
        "guided-pilot-scoping.yml",
    ],
    "docs/ADAPTERS.md": [
        "mechanical, never judgmental",
        "Interpretation stays in the\npolicy",
        "not as a verdict",
        "do not verify the authenticity",
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

INDEX_SECTIONS = ("documents", "examples", "policies", "tools", "ci", "assets")


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

    expected = f"aos-workflow-gate@v{version}"
    data = json.loads(read_text("docs.json"))
    documents = list(data.get("documents", []))
    found_current = False
    for path in documents:
        text = read_text(path)
        for match in re.finditer(
            r"aos-workflow-gate@v[0-9][^\s\"'`)\\]*", text
        ):
            if match.group(0) != expected:
                fail(
                    f"{path} references stale version {match.group(0)!r}; "
                    f"current is {expected!r}"
                )
            found_current = True
    if not found_current:
        fail(f"no document references the current version tag {expected!r}")


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
        "issues/new?template=guided-pilot-scoping.yml",
        "Self-Test Mode",
        "must not contain control characters",
        "AOS_GATE_WORKSPACE: ${{ github.workspace }}",
        "wait-for-checks",
        "Reproduce locally",
        "Replay path:",
        "name: aos-gate-evidence",
        "uses: actions/upload-artifact@"
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",
    )
    for snippet in required_action_snippets:
        if snippet not in action:
            fail(f"action.yml is missing required snippet: {snippet!r}")

    workflow = read_text(".github/workflows/aos-workflow-gate-self.yml")
    required_self_snippets = (
        "name: AOS Workflow Gate Self / advisory",
        "permissions:\n  contents: read\n  checks: read",
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
    check_examples()
    check_decision_fixture()
    check_repository_hygiene()
    check_action_surface()
    check_permissions_contract()
    check_version_consistency()
    print("public-surface check OK")


if __name__ == "__main__":
    main()
