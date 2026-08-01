from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUS_PATH = ROOT / "docs" / "RELEASE_STATUS.json"
MATRIX_PATH = ROOT / "docs" / "OPERATIONAL_MATRIX.md"

EXPECTED_STATUS_KEYS = {
    "schema_version",
    "published_version",
    "maturity",
    "distribution",
    "access",
    "default_mode",
    "product_claim_status",
    "production_use_recommended",
}
MATURITY_LEVELS = {
    "Preview",
    "Pilot",
    "Production candidate",
    "Production ready",
}


def _status() -> dict[str, Any]:
    return json.loads(STATUS_PATH.read_text(encoding="utf-8"))


def test_published_release_declares_bounded_maturity() -> None:
    status = _status()

    assert set(status) == EXPECTED_STATUS_KEYS
    assert status["schema_version"] == "aos-release-status/v0"
    assert status["maturity"] in MATURITY_LEVELS
    assert status["published_version"] == (
        ROOT / "docs" / "PUBLISHED_VERSION"
    ).read_text(encoding="utf-8").strip()
    assert status["distribution"] == "public_self_serve"
    assert status["access"] == "free"
    assert status["default_mode"] == "advisory"
    assert status["product_claim_status"] == "NO_GO"
    assert status["production_use_recommended"] is False


def test_preview_does_not_claim_production_readiness() -> None:
    status = _status()
    maturity = (ROOT / "docs" / "MATURITY.md").read_text(encoding="utf-8")
    normalized = " ".join(maturity.split())

    assert status["maturity"] == "Preview"
    assert "Current maturity: **Preview**." in maturity
    assert "Do not let it block production changes without human review." in normalized
    assert "Tests cannot promote maturity by themselves." in maturity


def test_operational_matrix_references_existing_test_functions() -> None:
    matrix = MATRIX_PATH.read_text(encoding="utf-8")
    node_ids = sorted(
        set(re.findall(r"(tests/[a-z0-9_./]+::test_[a-z0-9_]+)", matrix))
    )

    assert len(node_ids) >= 12
    for node_id in node_ids:
        path_text, function = node_id.split("::", 1)
        path = ROOT / path_text
        assert path.is_file(), node_id
        source = path.read_text(encoding="utf-8")
        assert re.search(
            rf"^def {re.escape(function)}\(",
            source,
            re.MULTILINE,
        ), node_id

    assert "not external field results" in matrix
