"""Regression tests for the preregistered mass-market value study."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

import tools.mass_value_study as study
from tools.mass_value_study import _aggregate, _derive_observation, _wilson

ROOT = Path(__file__).resolve().parents[1]


def _item(language: str) -> dict[str, Any]:
    return {
        "default_branch": "main",
        "github_primary_language": language,
        "repository": f"example/{language.lower()}",
        "search_language": language,
        "star_band": "10_99",
    }


def _raw(*, root_names: list[str]) -> dict[str, Any]:
    return {
        "defaultBranchRef": {"target": {"oid": "a" * 40}},
        "root": {
            "entries": [
                {"name": name, "oid": f"oid-{index}", "type": "blob"}
                for index, name in enumerate(root_names)
            ],
            "oid": "root-oid",
        },
    }


def _blob(text: str) -> dict[str, Any]:
    return {"byteSize": len(text), "oid": "blob-oid", "text": text}


def test_wilson_interval_contains_point_estimate() -> None:
    interval = _wilson(70, 100)

    assert interval["point"] == 0.7
    assert interval["lower"] is not None
    assert interval["upper"] is not None
    assert interval["lower"] < interval["point"] < interval["upper"]


def test_node_build_without_tests_is_coverage_gap_candidate() -> None:
    raw = _raw(root_names=["package.json", "src"])
    raw["package"] = _blob(
        json.dumps({"scripts": {"build": "tsc", "lint": "eslint ."}})
    )

    observed = _derive_observation(_item("TypeScript"), raw)

    assert observed["supported"] is True
    assert observed["behavioral_surface"] is False
    assert observed["coverage_gap_candidate"] is True
    assert observed["verdict_proxy"] == "WARN"
    assert observed["wrapper_only_candidate"] is False
    assert "scripts" not in observed


def test_node_test_script_is_behavioral_wrapper_candidate() -> None:
    raw = _raw(root_names=["package.json", "src", "test"])
    raw["package"] = _blob(
        json.dumps({"scripts": {"build": "tsc", "test": "vitest run"}})
    )

    observed = _derive_observation(_item("JavaScript"), raw)

    assert observed["behavioral_surface"] is True
    assert observed["coverage_gap_candidate"] is False
    assert observed["verdict_proxy"] == "PASS"
    assert observed["wrapper_only_candidate"] is True


def test_python_test_tree_is_detected_without_executing_repository() -> None:
    raw = _raw(root_names=["pyproject.toml", "src", "tests"])
    raw["pyproject"] = _blob("[project]\nname = 'sample'\n")
    raw["tests_dir"] = {
        "entries": [{"name": "test_app.py", "oid": "test-oid", "type": "blob"}],
        "oid": "tests-oid",
    }

    observed = _derive_observation(_item("Python"), raw)

    assert observed["ecosystems"] == ["Python"]
    assert observed["behavioral_surface"] is True
    assert observed["head_sha"] == "a" * 40
    assert observed["relevant_blobs"]["pyproject"]["oid"] == "blob-oid"


def test_aggregate_preserves_denominators_and_incomplete_rate() -> None:
    rows = [
        {
            "behavioral_surface": True,
            "complete": True,
            "coverage_gap_candidate": False,
            "supported": True,
            "wrapper_only_candidate": True,
        },
        {
            "behavioral_surface": False,
            "complete": False,
            "coverage_gap_candidate": True,
            "supported": True,
            "wrapper_only_candidate": False,
        },
        {
            "behavioral_surface": False,
            "complete": True,
            "coverage_gap_candidate": False,
            "supported": False,
            "wrapper_only_candidate": False,
        },
    ]

    result = _aggregate(rows)

    assert result["repositories"] == 3
    assert result["detection_rate"] == 0.6667
    assert result["behavioral_surface_rate"] == 0.3333
    assert result["coverage_gap_candidate_rate"] == 0.3333
    assert result["incomplete_rate"] == 0.3333


def test_manifest_forbids_public_repository_execution() -> None:
    manifest = json.loads(
        (ROOT / "benchmarks" / "mass-market" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    assert manifest["public_repository_execution"] == "forbidden_without_isolation"
    assert (
        "no public repository code is executed"
        in manifest["controlled_execution"]["scope"]
    )
    assert manifest["sample"]["target_repositories"] == 500


def test_search_query_enforces_preregistered_data_cutoff() -> None:
    manifest = json.loads(
        (ROOT / "benchmarks" / "mass-market" / "manifest.json").read_text(
            encoding="utf-8"
        )
    )

    query = study._search_query("Python", "1..9", manifest)

    assert "pushed:>=2026-01-01" in query
    assert "pushed:<=2026-07-22" in query


def test_graphql_partial_data_preserves_frozen_unavailable_repo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout=json.dumps(
                {
                    "data": {"r0": None},
                    "errors": [{"message": "repository unavailable"}],
                }
            ),
            stderr="gh: repository unavailable",
        )

    monkeypatch.setattr(study.subprocess, "run", fake_run)

    response = study._gh_json(["graphql"])

    assert response["data"]["r0"] is None
