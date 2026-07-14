"""Internal readiness evidence that cannot be promoted to user evidence."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.value_gate import (
    PRODUCT_READINESS_SCHEMA,
    _validate_product_readiness,
)

ROOT = Path(__file__).resolve().parents[1]
READINESS = ROOT / "benchmarks" / "value" / "product-test-readiness.json"


def _readiness() -> dict[str, Any]:
    value = json.loads(READINESS.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_readiness_manifest_references_real_evidence() -> None:
    manifest = _readiness()
    assert manifest["schema_version"] == PRODUCT_READINESS_SCHEMA
    _validate_product_readiness(manifest)

    for check in manifest["checks"]:
        for reference in check["evidence"]:
            path_text, _, node_id = reference.partition("::")
            path = ROOT / path_text
            assert path.is_file(), reference
            if node_id:
                text = path.read_text(encoding="utf-8")
                assert f"def {node_id}(" in text, reference


def test_wheel_installs_in_isolated_target(tmp_path: Path) -> None:
    wheel_dir = tmp_path / "wheel"
    wheel_dir.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(ROOT),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    wheels = list(wheel_dir.glob("aos_workflow_gate-*.whl"))
    assert len(wheels) == 1

    site = tmp_path / "site"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            "--no-deps",
            "--no-index",
            "--target",
            str(site),
            str(wheels[0]),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe = site / "_aos_clean_room_probe.py"
    probe.write_text(
        "from aos_workflow_gate.cli import main\n"
        "raise SystemExit(main(['--version']))\n",
        encoding="utf-8",
        newline="\n",
    )
    result = subprocess.run(
        [sys.executable, "-I", str(probe)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "0.36.0"
