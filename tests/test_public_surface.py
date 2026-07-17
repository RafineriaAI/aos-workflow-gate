from __future__ import annotations

import json
from pathlib import Path

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
    for section in ("documents", "examples", "policies", "tools", "ci"):
        for item in data.get(section, []):
            assert (ROOT / item).exists(), f"docs.json references missing {item}"


def test_readme_license_and_local_check_are_renderable() -> None:
    readme = read_text("README.md")
    assert README_LOCAL_HYGIENE_BLOCK in readme
    assert "```bash\npython tools/check_public_surface.py\n```" in readme
    assert "Apache-2.0. See [LICENSE](LICENSE)." in readme
    assert "MIT. See [LICENSE](LICENSE)." not in readme


def test_readme_leads_with_product_value_before_validation_detail() -> None:
    readme = read_text("README.md")
    proof = readme.index("Green checks can still miss a merge-control gap.")
    first_run = readme.index("## Try it on any public PR")
    validation = readme.index("## Validation status")
    documentation = readme.index("## Documentation")

    assert proof < first_run < validation < documentation
    assert "docs/assets/readme-contrast.png" in readme
    assert readme.count("uses: RafineriaAI/aos-workflow-gate@v") == 1
    for stale_heading in (
        "## Current status",
        "## Core idea",
        "## Practical use case",
        "## Documentation map",
    ):
        assert stale_heading not in readme


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


def test_action_and_self_workflow_are_bounded() -> None:
    action = read_text("action.yml")
    assert 'using: "composite"' in action
    assert "UNSIGNED_NOT_OFFICIAL" in action
    assert 'default: "false"' in action

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
        "in-toto attestations",
        "OpenSSF Scorecard",
        "UNSIGNED_NOT_OFFICIAL",
    ):
        assert snippet in standards
