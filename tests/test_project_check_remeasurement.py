"""Tests for the metadata-only Project Check remeasurement."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.mass_value_study import _canonical_digest
from tools.project_check_remeasurement import _result, observe_tree

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "benchmarks" / "mass-market"


def _repository() -> dict[str, Any]:
    return {
        "head_sha": "a" * 40,
        "repository": "example/project",
    }


def _tree(*paths: str, truncated: bool = False) -> dict[str, Any]:
    return {
        "tree": [
            {
                "path": path,
                "sha": str(index) * 40,
                "type": "blob",
            }
            for index, path in enumerate(paths, 1)
        ],
        "truncated": truncated,
    }


def _loader(
    contents: dict[str, bytes],
) -> Callable[[dict[str, Any]], bytes]:
    def load(entry: dict[str, Any]) -> bytes:
        path = entry["path"]
        return contents.get(path, b"")

    return load


def test_nested_declared_test_command_resolves_root_only_warning() -> None:
    response = _tree("package.json", "packages/api/package.json")
    contents = {
        "package.json": json.dumps({"private": True}).encode(),
        "packages/api/package.json": json.dumps(
            {"scripts": {"test": "node --test"}}
        ).encode(),
    }

    result = observe_tree(
        _repository(),
        response,
        load_blob=_loader(contents),
        adjudication="definite_test_surface",
    )

    assert result["classification"] == "resolved_by_nested_command"
    assert result["declared_test_checks"] == [
        {"id": "node.test@packages/api", "working_directory": "packages/api"}
    ]


def test_test_file_without_supported_command_remains_precise_warning() -> None:
    response = _tree("package.json", "src/widget.test.ts")
    contents = {"package.json": json.dumps({"scripts": {"build": "tsc"}}).encode()}

    result = observe_tree(
        _repository(),
        response,
        load_blob=_loader(contents),
        adjudication="definite_test_surface",
    )

    assert result["classification"] == "no_supported_runnable_command"
    assert result["declared_test_checks"] == []


def test_python_nested_test_surface_is_detected_without_execution() -> None:
    response = _tree(
        "README.md",
        "services/api/pyproject.toml",
        "services/api/tests/test_app.py",
    )
    contents = {
        "services/api/pyproject.toml": (b'[project]\nname = "api"\nversion = "0.1.0"\n')
    }

    result = observe_tree(
        _repository(),
        response,
        load_blob=_loader(contents),
    )

    assert result["classification"] == "resolved_by_nested_command"
    assert result["project_roots"] == ["services/api"]


def test_truncated_tree_is_inconclusive_and_fetches_nothing() -> None:
    result = observe_tree(
        _repository(),
        _tree("package.json", truncated=True),
        load_blob=lambda _: (_ for _ in ()).throw(AssertionError("not called")),
    )

    assert result["classification"] == "inconclusive_truncated_tree"
    assert result["complete"] is False


def test_result_separates_reason_reduction_from_complete_discovery() -> None:
    observations: list[dict[str, Any]] = [
        {
            "adjudication": "definite_test_surface",
            "classification": "resolved_by_nested_command",
            "complete": True,
            "declared_test_checks": [{"id": "node.test"}],
            "nested_discovery_complete": True,
            "repository": "example/a",
        },
        {
            "adjudication": "definite_test_surface",
            "classification": "resolved_by_nested_command",
            "complete": True,
            "declared_test_checks": [{"id": "node.test"}],
            "nested_discovery_complete": False,
            "repository": "example/b",
        },
        {
            "adjudication": None,
            "classification": "no_supported_runnable_command",
            "complete": True,
            "declared_test_checks": [],
            "nested_discovery_complete": True,
            "repository": "example/c",
        },
    ]
    result = _result(
        {
            "claim_boundary": "bounded",
            "selection": {"expected_repositories": 3},
            "study_id": "test",
        },
        {"status": "PRIOR"},
        observations,
    )

    metrics = result["metrics"]
    assert result["status"] == "MEASURED_FALSE_WARNING_RISK_REDUCTION"
    assert metrics["nested_command_resolutions"] == 2
    assert metrics["complete_nested_command_resolutions"] == 1
    assert metrics["bounded_discovery_incomplete"] == 1
    assert metrics["definite_surfaces_with_supported_command"] == 2
    assert metrics["definite_surfaces_with_complete_supported_command"] == 1


def test_committed_remeasurement_reaggregates_offline_without_blob_content() -> None:
    manifest = json.loads(
        (BASE / "project-check-remeasurement-manifest.json").read_text(
            encoding="utf-8"
        )
    )
    gap_audit = json.loads(
        (BASE / "gap-audit.json").read_text(encoding="utf-8")
    )
    adjudication = json.loads(
        (BASE / "gap-audit-adjudication.json").read_text(encoding="utf-8")
    )
    committed = json.loads(
        (BASE / "project-check-remeasurement.json").read_text(encoding="utf-8")
    )

    assert _canonical_digest(gap_audit) == manifest["source_gap_audit_digest"]
    assert (
        _canonical_digest(adjudication)
        == manifest["source_adjudication_digest"]
    )
    fresh = _result(manifest, gap_audit, committed["observations"])
    assert fresh["metrics"] == committed["metrics"]
    assert fresh["observations"] == committed["observations"]
    assert fresh["status"] == committed["status"]
    assert fresh["manifest_digest"] == committed["manifest_digest"]

    def keys(value: Any) -> set[str]:
        if isinstance(value, dict):
            return set(value).union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value))
        return set()

    assert keys(committed).isdisjoint({"blob", "content", "raw", "scripts"})
