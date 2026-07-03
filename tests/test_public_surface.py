from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_docs_json_paths_exist() -> None:
    data = json.loads(read_text("docs.json"))
    for section in ("documents", "examples", "policies", "tools", "ci"):
        for item in data.get(section, []):
            assert (ROOT / item).exists(), f"docs.json references missing {item}"


def test_readme_license_and_local_check_are_renderable() -> None:
    readme = read_text("README.md")
    assert "```bash\npython tools/check_public_surface.py\n```" in readme
    assert "Apache-2.0. See [LICENSE](LICENSE)." in readme
    assert "MIT. See [LICENSE](LICENSE)." not in readme


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
