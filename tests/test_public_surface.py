from __future__ import annotations

import json
import tomllib
from pathlib import Path

from tools.check_public_surface import (
    INDEX_SECTIONS,
    _expected_index_paths,
    check_action_examples,
    check_cli_examples,
    check_local_links,
    merge_metadata_issues,
)

ROOT = Path(__file__).resolve().parents[1]

README_LOCAL_HYGIENE_BLOCK = """Run the local hygiene checks with:

```bash
python -m ruff check .
python -m mypy
python -m pytest
python tools/check_public_surface.py
```"""


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_docs_json_paths_exist() -> None:
    data = json.loads(read_text("docs.json"))
    for section in INDEX_SECTIONS:
        for item in data.get(section, []):
            assert (ROOT / item).exists(), f"docs.json references missing {item}"


def test_docs_index_covers_the_complete_public_surface() -> None:
    data = json.loads(read_text("docs.json"))
    indexed = [
        item
        for section in INDEX_SECTIONS
        for item in data.get(section, [])
    ]

    assert data["status"] == "public-advisory-preview"
    assert len(indexed) == len(set(indexed))
    assert _expected_index_paths() <= set(indexed)


def test_documentation_links_and_examples_match_the_product() -> None:
    check_local_links()
    check_cli_examples()
    check_action_examples()


def test_readme_license_and_local_check_are_renderable() -> None:
    readme = read_text("README.md")
    assert README_LOCAL_HYGIENE_BLOCK in readme
    assert "```bash\npython tools/check_public_surface.py\n```" in readme
    assert "Apache-2.0. See [LICENSE](LICENSE)." in readme
    assert "MIT. See [LICENSE](LICENSE)." not in readme


def test_readme_leads_with_product_value_before_validation_detail() -> None:
    readme = read_text("README.md")
    proof = readme.index("AOS verifies the gate, not the code.")
    first_run = readme.index("## Try it on any public PR")
    validation = readme.index("## Validation status")
    documentation = readme.index("## Documentation")

    assert proof < first_run < validation < documentation
    assert "docs/assets/readme-contrast.png" in readme
    assert "docs/assets/readme-contrast-mobile.png" in readme
    assert '<source media="(max-width: 600px)"' in readme
    assert readme.count("uses: RafineriaAI/aos-workflow-gate@v") == 1
    assert (ROOT / "docs/assets/readme-contrast.png").exists()
    assert (ROOT / "docs/assets/readme-contrast-mobile.png").exists()
    for stale_heading in (
        "## Current status",
        "## Core idea",
        "## Practical use case",
        "## Documentation map",
    ):
        assert stale_heading not in readme


def test_business_positioning_is_consistent_and_bounded() -> None:
    category_paths = (
        "README.md",
        "action.yml",
        "docs/ONE_PAGER.md",
        "docs/SCOPE.md",
        "docs/COMPARISON.md",
    )
    for path in category_paths:
        normalized = " ".join(read_text(path).lower().split())
        assert "pre-merge control assurance" in normalized, path

    core_gap = (
        "control that is missing, stale, produced by the wrong app, or "
        "modified by the same PR"
    )
    for path in ("README.md", "action.yml", "docs/ONE_PAGER.md", "docs/index.html"):
        normalized = " ".join(read_text(path).split())
        assert core_gap in normalized, path

    for path in ("README.md", "docs/ONE_PAGER.md", "docs/index.html"):
        assert "AOS verifies the gate, not the code." in read_text(path), path

    buyer = read_text("docs/BUYER_FAQ.md")
    buyer_normalized = " ".join(buyer.split())
    value = read_text("docs/VALUE.md")
    funnel = read_text("docs/FUNNEL.md")
    metrics = read_text("docs/VALUE_METRICS.md")

    assert "individual developer is a weak paid ICP" in buyer_normalized
    assert "There is no active paid offering." in buyer
    assert "low-frequency, potentially high-cost" in value
    assert "Policy packs alone are too copyable" in value
    assert "## Commercialization gate" in funnel
    for metric in (
        "Actionable rate",
        "Decision-change rate",
        "30-day retention",
    ):
        assert metric in metrics

    pyproject = tomllib.loads(read_text("pyproject.toml"))
    assert pyproject["project"]["description"] == (
        "Pre-merge control assurance with exact-commit replayable evidence."
    )


def test_kernel_relationship_is_standalone_and_bounded() -> None:
    architecture = read_text("docs/ARCHITECTURE.md")
    scope = read_text("docs/SCOPE.md")
    governance = read_text("docs/RELEASE_GOVERNANCE.md")

    assert "does not prove this package's source-status rules" in architecture
    assert "No artifact produced here is kernel-generated" in scope
    assert "shared vocabulary and\ndesign lineage are not sufficient" in governance

    for stale in (
        "workflow gate layer around `aos-kernel`",
        "Formal verdict semantics remain in the kernel",
    ):
        assert stale not in governance


def test_ci_uses_pinned_actions_and_no_persisted_credentials() -> None:
    workflow = read_text(".github/workflows/aos-workflow-gate-ci.yml")
    checkout = "uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd"
    setup_python = "uses: actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
    assert checkout in workflow
    assert setup_python in workflow
    assert "persist-credentials: false" in workflow
    assert "python -m ruff check ." in workflow
    assert "python -m mypy" in workflow
    assert "python -m pytest" in workflow


def test_release_governance_names_required_check() -> None:
    governance = read_text("docs/RELEASE_GOVERNANCE.md")
    assert "AOS Workflow Gate CI / validate" in governance
    assert "no Lean build is required" in governance
    assert "Do not delete, recreate, or force-push a published `v*` tag" in governance

    assert "--subject" in governance
    assert "--body" in governance


def test_merge_metadata_hygiene_rejects_branch_leaks() -> None:
    clean = (
        "Release metadata integrity and v0.37.1\n\n"
        "Enforce public metadata."
    )
    default = "Merge pull request #71 from acme/temporary-release-branch"

    assert merge_metadata_issues(clean) == []
    assert merge_metadata_issues(default) == [
        "default merge subject exposes a branch",
    ]

    assert merge_metadata_issues("Merge branch 'temporary-release-branch'")


def test_action_and_self_workflow_are_bounded() -> None:
    action = read_text("action.yml")
    assert 'using: "composite"' in action
    assert "UNSIGNED_NOT_OFFICIAL" in action
    assert 'default: "false"' in action
    assert "GATE_SARIF: ${{ inputs.sarif }}" in action
    assert "decision-contrast" in action
    assert "incremental-gap" in action

    workflow = read_text(".github/workflows/aos-workflow-gate-self.yml")
    assert "permissions:\n  contents: read" in workflow
    assert "  checks: read" in workflow
    assert "  actions: read" in workflow
    assert "  pull-requests: read" in workflow
    assert "  statuses: read" in workflow
    assert "persist-credentials: false" in workflow
    pinned_upload = (
        "uses: actions/upload-artifact@"
        "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"
    )
    assert pinned_upload in workflow


def test_standards_compatibility_is_indexed_and_bounded() -> None:
    data = json.loads(read_text("docs.json"))
    assert "docs/STANDARDS_COMPATIBILITY.md" in data["documents"]

    readme = read_text("README.md")
    assert "docs/STANDARDS_COMPATIBILITY.md" in readme

    standards = read_text("docs/STANDARDS_COMPATIBILITY.md")
    for snippet in (
        "not a compliance claim",
        "SLSA",
        "SPDX",
        "CycloneDX",
        "SARIF 2.1.0",
        "in-toto Statement v1",
        "OpenSSF Scorecard",
        "UNSIGNED_NOT_OFFICIAL",
    ):
        assert snippet in standards


def test_dev_extra_is_a_complete_clean_room_environment() -> None:
    pyproject = tomllib.loads(read_text("pyproject.toml"))
    dev = pyproject["project"]["optional-dependencies"]["dev"]

    for package in ("mypy", "pytest", "ruff", "setuptools", "wheel"):
        assert any(requirement.startswith(package) for requirement in dev)


def test_contributor_onboarding_and_ownership_are_explicit() -> None:
    contributing = read_text("CONTRIBUTING.md")
    development = read_text("docs/DEVELOPMENT.md")
    codeowners = read_text(".github/CODEOWNERS")
    template = read_text(".github/pull_request_template.md")

    assert 'python -m pip install -e ".[dev]"' in contributing
    assert "## Repository map" in development
    assert "## Non-negotiable invariants" in development
    assert "* @RafineriaAI" in codeowners
    assert "## Verification" in template
    assert "## Compatibility" in template


def test_current_status_docs_do_not_describe_the_bootstrap_phase() -> None:
    assert "public bootstrap" not in read_text("SECURITY.md")
    assert "planned architecture" not in read_text("docs/ARCHITECTURE.md")
    assert "once implementation starts" not in read_text("CONTRIBUTING.md")
    assert "## Next milestone: external value validation" in read_text(
        "ROADMAP.md"
    )
