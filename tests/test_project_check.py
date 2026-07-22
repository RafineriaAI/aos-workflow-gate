from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from aos_workflow_gate import canonical, cli
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.policy import load_policy
from aos_workflow_gate.project_check import (
    FAILED,
    LIMITED,
    QUALITY_WARNING,
    SUCCESS,
    CheckRun,
    CheckSpec,
    ProjectPlan,
    _status,
    build_bundle,
    check_project,
    discover_project,
)
from aos_workflow_gate.source_contract import validate_source_v0

ROOT = Path(__file__).resolve().parents[1]


def _write(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _python_project(tmp_path: Path, *, expected: int = 2) -> Path:
    root = tmp_path / "hello-app"
    root.mkdir()
    _write(
        root,
        "pyproject.toml",
        '[project]\nname = "hello-app"\nversion = "0.1.0"\n\n'
        '[tool.pytest.ini_options]\ntestpaths = ["tests"]\n',
    )
    _write(root, "app.py", "def answer():\n    return 2\n")
    _write(
        root,
        "tests/test_app.py",
        "import os\nfrom app import answer\n\ndef test_answer():\n"
        "    assert os.environ['CI'] == 'true'\n"
        "    assert os.environ['NO_COLOR'] == '1'\n"
        f"    assert answer() == {expected}\n",
    )
    return root


def _decision(source: dict[str, object]):  # type: ignore[no-untyped-def]
    policy = load_policy(ROOT / "aos_workflow_gate" / "packs" / "project-check.yml")
    return evaluate(build_bundle(source), policy)


def test_project_check_passes_without_git_when_build_and_tests_pass(
    tmp_path: Path,
) -> None:
    project = _python_project(tmp_path)

    result = check_project(project, timeout_seconds=30)
    source = result.source

    assert not (project / ".git").exists()
    assert not list(project.rglob("__pycache__"))
    assert source["status"] == SUCCESS
    assert validate_source_v0(source) == source
    assert _decision(source).verdict == "PASS"
    identity = source["identity"]
    assert isinstance(identity, dict)
    assert identity["ecosystems"] == ["Python"]
    assert identity["snapshot_complete"] is True
    assert [run["id"] for run in identity["checks"]] == [
        "python.compile",
        "python.tests",
    ]
    assert identity["checks"][0]["command"][0] == "python"
    assert str(Path(sys.executable).parent) not in json.dumps(identity)


def test_project_check_blocks_on_reproduced_test_failure(tmp_path: Path) -> None:
    project = _python_project(tmp_path, expected=3)

    result = check_project(project, timeout_seconds=30)
    decision = _decision(result.source)

    assert result.source["status"] == FAILED
    assert decision.verdict == "BLOCK"
    assert decision.reasons[0].rule == "project_check_failed"
    assert any(run.spec.check_id == "python.tests" for run in result.runs)
    failed = next(run for run in result.runs if run.state == "failed")
    assert "1 failed" in failed.preview
    assert "1 failed" not in json.dumps(result.source)


def test_project_check_warns_when_no_behavioral_test_exists(tmp_path: Path) -> None:
    project = tmp_path / "small-script"
    project.mkdir()
    _write(project, "main.py", "print('hello')\n")

    result = check_project(project, timeout_seconds=30)
    decision = _decision(result.source)

    assert result.source["status"] == LIMITED
    assert decision.verdict == "WARN"
    assert decision.reasons[0].rule == "project_verification_limited"
    assert "behavioral test" in str(result.source["summary"])
    assert decision.reasons[0].detail == result.source["summary"]


def test_node_plan_uses_declared_scripts_without_installing_dependencies(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = tmp_path / "web-app"
    project.mkdir()
    _write(
        project,
        "package.json",
        json.dumps(
            {
                "scripts": {
                    "build": "vite build",
                    "test": "vitest run",
                    "lint": "eslint .",
                }
            }
        ),
    )
    monkeypatch.setattr("aos_workflow_gate.project_check.shutil.which", lambda _: "npm")

    plan = discover_project(project)

    assert plan.ecosystems == ("Node.js",)
    assert [spec.check_id for spec in plan.checks] == [
        "node.build",
        "node.test",
        "node.lint",
    ]
    assert [spec.command for spec in plan.checks] == [
        ("npm", "run", "build"),
        ("npm", "run", "test"),
        ("npm", "run", "lint"),
    ]


def test_project_evidence_contains_digests_not_raw_output(tmp_path: Path) -> None:
    project = _python_project(tmp_path)
    secret = "DO-NOT-STORE-THIS"
    _write(
        project,
        "tests/test_app.py",
        "from app import answer\n\n"
        f"def test_answer():\n    print({secret!r})\n    assert answer() == 2\n",
    )

    result = check_project(project, timeout_seconds=30)
    encoded = json.dumps(result.source, sort_keys=True)

    assert secret not in encoded
    assert "stdout_digest" in encoded
    assert result.source["digest"] == canonical.digest(result.source["identity"])


def test_check_project_cli_writes_replayable_local_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _python_project(tmp_path)
    monkeypatch.chdir(project)

    exit_code = cli.main(["check-project"])

    assert exit_code == 0
    record_path = project / ".aos-check" / "gate-decision.json"
    bundle_path = project / ".aos-check" / "bundle.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert record["verdict"] == "PASS"
    assert record["subject"]["repository"] == "local/hello-app"
    assert record["input_bundle_digest"] == canonical.digest(bundle)
    assert (
        cli.main(["verify", "--input", str(record_path), "--bundle", str(bundle_path)])
        == 0
    )
    assert record["observation"]["project_check"]["ecosystems"] == ["Python"]


def test_custom_verifier_can_check_an_unrecognized_folder(tmp_path: Path) -> None:
    project = tmp_path / "custom-app"
    project.mkdir()
    _write(project, "data.txt", "hello\n")

    result = check_project(
        project,
        timeout_seconds=30,
        custom_command=(sys.executable, "-c", "raise SystemExit(0)"),
    )

    assert result.source["status"] == LIMITED
    assert result.runs[0].spec.check_id == "custom.verifier"


def test_quality_failure_warns_instead_of_blocking() -> None:
    test = CheckSpec("node.test", "Node tests", "test", ("npm", "run", "test"))
    quality = CheckSpec("node.lint", "Node lint", "quality", ("npm", "run", "lint"))
    plan = ProjectPlan(("Node.js",), (test, quality), ())
    empty_digest = "sha256:" + "0" * 64
    runs = (
        CheckRun(
            test,
            "passed",
            0,
            10,
            empty_digest,
            empty_digest,
            0,
            0,
            "",
        ),
        CheckRun(
            quality,
            "failed",
            1,
            10,
            empty_digest,
            empty_digest,
            0,
            0,
            "lint failure",
        ),
    )

    assert _status(plan, runs, snapshot_complete=True) == QUALITY_WARNING


def test_javascript_src_folder_is_not_misclassified_as_python(tmp_path: Path) -> None:
    project = tmp_path / "web-app"
    project.mkdir()
    _write(project, "src/index.js", "console.log('hello')\n")
    _write(
        project,
        "package.json",
        json.dumps({"scripts": {"test": "node --test"}}),
    )

    plan = discover_project(project)

    assert plan.ecosystems == ("Node.js",)
    assert all(not check.check_id.startswith("python.") for check in plan.checks)


def test_missing_behavioral_test_outranks_quality_warning() -> None:
    quality = CheckSpec("node.lint", "Node lint", "quality", ("npm", "run", "lint"))
    plan = ProjectPlan(
        ("Node.js",),
        (quality,),
        ("No runnable behavioral test was discovered.",),
    )
    empty_digest = "sha256:" + "0" * 64
    runs = (
        CheckRun(
            quality,
            "failed",
            1,
            10,
            empty_digest,
            empty_digest,
            0,
            0,
            "lint failure",
        ),
    )

    assert _status(plan, runs, snapshot_complete=True) == LIMITED
