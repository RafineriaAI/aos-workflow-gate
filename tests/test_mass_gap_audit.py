"""Regression tests for exact-SHA missing-test-surface path auditing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.mass_gap_audit import _observe, is_test_path

ROOT = Path(__file__).resolve().parents[1]


def _manifest() -> dict[str, Any]:
    return json.loads(
        (ROOT / "benchmarks" / "mass-market" / "gap-audit-manifest.json").read_text(
            encoding="utf-8"
        )
    )


def _repository() -> dict[str, Any]:
    return {
        "head_sha": "a" * 40,
        "repository": "example/project",
        "search_language": "TypeScript",
        "star_band": "10..99",
    }


def test_test_path_matching_uses_segments_and_ignores_vendored_paths() -> None:
    manifest = _manifest()

    assert is_test_path("tests/test_app.py", manifest)
    assert is_test_path("src/widget.spec.ts", manifest)
    assert is_test_path("packages/api/vitest.config.ts", manifest)
    assert not is_test_path("src/latest_release.ts", manifest)
    assert not is_test_path("contest/data.py", manifest)
    assert not is_test_path("node_modules/pkg/tests/test.js", manifest)


def test_complete_tree_with_test_path_contradicts_missing_surface() -> None:
    response = {
        "tree": [
            {"path": "src/index.ts", "type": "blob"},
            {"path": "src/index.test.ts", "type": "blob"},
        ],
        "truncated": False,
    }

    result = _observe(_repository(), response, _manifest())

    assert result["classification"] == "contradicted_by_paths"
    assert result["test_path_count"] == 1
    assert result["complete"] is True


def test_truncated_tree_is_inconclusive_even_when_no_test_path_is_seen() -> None:
    response = {
        "tree": [{"path": "src/index.ts", "type": "blob"}],
        "truncated": True,
    }

    result = _observe(_repository(), response, _manifest())

    assert result["classification"] == "inconclusive"
    assert result["complete"] is False
