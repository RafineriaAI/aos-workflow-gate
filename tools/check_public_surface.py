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
        "Public bootstrap.",
        "It is not implemented yet.",
        "No production, compliance, signing, SLSA, or security-audit claim",
        README_LOCAL_HYGIENE_BLOCK,
        "```bash\npython tools/check_public_surface.py\n```",
        "Apache-2.0. See [LICENSE](LICENSE).",
        "docs/RELEASE_GOVERNANCE.md",
        "docs/STANDARDS_COMPATIBILITY.md",
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
    ],
    "ROADMAP.md": [
        "## Phase 0: public bootstrap",
        "## Phase 1: local MVP CLI",
        "These are future layers, not current claims.",
    ],
}

UNSUPPORTED_POSITIVE_CLAIMS = [
    re.compile(r"\bis production-ready\b", re.IGNORECASE),
    re.compile(r"\bprovides compliance certification\b", re.IGNORECASE),
    re.compile(r"\bcertifies compliance\b", re.IGNORECASE),
    re.compile(r"\bproves (?:the )?repository is secure\b", re.IGNORECASE),
    re.compile(r"\bformally proves workflow correctness\b", re.IGNORECASE),
]

INDEX_SECTIONS = ("documents", "examples", "policies", "tools", "ci")


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
    checked_paths = []
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
        fail(
            "example signal bundle must stay draft-0 until the CLI contract "
            "is implemented"
        )
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
    )
    for snippet in required_workflow_snippets:
        if snippet not in workflow:
            fail(f"workflow is missing required hygiene snippet: {snippet!r}")

    if (ROOT / ".github/workflows/public-surface.yml").exists():
        fail(
            "legacy public-surface workflow should be replaced by "
            "aos-workflow-gate-ci.yml"
        )


def main() -> None:
    check_docs_index()
    check_required_snippets()
    check_claim_boundary()
    check_examples()
    check_repository_hygiene()
    print("public-surface check OK")


if __name__ == "__main__":
    main()
