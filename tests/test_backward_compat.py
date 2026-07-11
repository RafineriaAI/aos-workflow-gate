"""Backward and forward compatibility binding.

Historical release evidence (real triples shipped with earlier
releases, committed verbatim under ``tests/data/historical``) pins the
compatibility contract:

- **Digest replay is forever**: every historical record must self-verify
  and bind to its bundle, on every CI run, regardless of verifier
  version.
- **Semantic replay is version-scoped**: re-evaluating a historical
  bundle+policy with the current evaluator must reproduce the verdict;
  any additional reasons must come only from rules that did not exist
  when the record was written (additive evolution, disclosed — never a
  silently changed meaning).
- **Verifier substitution is detectable**: current records carry the
  verifier manifest content address; historical records predate it and
  ``verify`` says so instead of guessing.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import canonical
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.evidence import verify_record
from aos_workflow_gate.manifest import (
    verifier_manifest,
    verifier_manifest_digest,
)
from aos_workflow_gate.policy import load_policy

ROOT = Path(__file__).resolve().parents[1]
HISTORICAL = ROOT / "tests" / "data" / "historical"
ERAS = ("v0.15", "v0.16")

# rules added after the historical records were written; only these may
# appear as extra reasons under the current evaluator
_ADDITIVE_RULES = {"no_required_sources", "incomplete_collection"}


def _load(era: str, kind: str) -> Any:
    return json.loads(
        (HISTORICAL / f"{era}-release-gate-{kind}.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.mark.parametrize("era", ERAS)
def test_digest_replay_is_forever(era: str) -> None:
    record = _load(era, "decision")
    bundle = _load(era, "bundle")
    assert verify_record(record), era
    assert record["input_bundle_digest"] == canonical.digest(bundle), era
    generator = record["generator"]
    assert "verifier_manifest_digest" not in generator, (
        "historical fixture unexpectedly carries a manifest digest"
    )


@pytest.mark.parametrize("era", ERAS)
def test_semantic_replay_is_version_scoped(era: str) -> None:
    record = _load(era, "decision")
    bundle = _load(era, "bundle")
    policy = load_policy(HISTORICAL / f"{era}-release-gate-policy.json")
    decision = evaluate(bundle, policy)
    assert decision.verdict == record["verdict"], era
    old_rules = {reason["rule"] for reason in record["reasons"]}
    new_rules = {reason.rule for reason in decision.reasons}
    assert new_rules - old_rules <= _ADDITIVE_RULES, (
        era, new_rules - old_rules
    )


def test_current_records_carry_the_verifier_manifest() -> None:
    record = json.loads(
        (ROOT / "examples" / "gate-decision.json").read_text(
            encoding="utf-8"
        )
    )
    digest = record["generator"]["verifier_manifest_digest"]
    assert digest == verifier_manifest_digest()
    manifest = verifier_manifest()
    assert manifest["manifest_digest"] == digest
    assert "evaluate.py" in manifest["files"]
    assert "manifest.py" in manifest["files"]


def test_manifest_detects_verifier_substitution(tmp_path: Path) -> None:
    """A record claiming a different manifest is distinguishable from
    one produced by this installation — content addressing only, no
    signing or authorship claim."""
    manifest = verifier_manifest()
    files = dict(manifest["files"])
    files["evaluate.py"] = "0" * 64  # substituted evaluator
    assert canonical.digest(files) != manifest["manifest_digest"]


def test_verify_cli_discloses_manifest_and_context(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from aos_workflow_gate.cli import main

    rc = main(
        ["verify",
         "--input", str(ROOT / "examples" / "gate-decision.json"),
         "--bundle", str(ROOT / "examples" / "github-pr-signal-bundle.json")]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "verifier: same manifest" in out
    assert "subject context:" in out

    rc = main(
        ["verify",
         "--input", str(HISTORICAL / "v0.16-release-gate-decision.json"),
         "--bundle", str(HISTORICAL / "v0.16-release-gate-bundle.json")]
    )
    out = capsys.readouterr().out
    assert rc == 0
    assert "predates manifest binding" in out
