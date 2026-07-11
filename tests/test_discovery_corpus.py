"""The frozen pain-discovery corpus must stay internally consistent.

Offline checks only — CI never touches the network. The corpus is
frozen data: these tests pin its structure, the deterministic
discovery/holdout split, the discovery-only scope of every candidate
policy summary, and the presence of negative results and noise
assessments (the DoD for evidence-led discovery).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "discovery"

sys.path.insert(0, str(ROOT))

from tools.discovery import split_of  # noqa: E402


def _manifest() -> dict:
    return json.loads(
        (CORPUS / "manifest.json").read_text(encoding="utf-8")
    )


def _analysis() -> dict:
    return json.loads(
        (CORPUS / "analysis.json").read_text(encoding="utf-8")
    )


def test_manifest_structure_and_boundary() -> None:
    manifest = _manifest()
    assert manifest["schema_version"] == "discovery-manifest-v0"
    assert "no code, no diffs, no comment bodies" in manifest["boundary"]
    assert manifest["pulls"], "the corpus must not be empty"
    for pull in manifest["pulls"]:
        assert isinstance(pull["repo"], str) and "/" in pull["repo"]
        assert isinstance(pull["number"], int)
        assert pull["split"] in ("discovery", "holdout")
        assert pull["merged_at"], "only merged PRs belong to the corpus"


def test_split_is_deterministic_and_recomputable() -> None:
    manifest = _manifest()
    for pull in manifest["pulls"]:
        assert pull["split"] == split_of(pull["repo"], pull["number"]), (
            f"{pull['repo']}#{pull['number']}: recorded split does not "
            "match the published rule"
        )


def test_both_splits_are_inhabited() -> None:
    splits = {pull["split"] for pull in _manifest()["pulls"]}
    assert splits == {"discovery", "holdout"}


def test_analysis_matches_manifest_membership() -> None:
    manifest_keys = {
        (pull["repo"], pull["number"]) for pull in _manifest()["pulls"]
    }
    analysis_keys = {
        (entry["repo"], entry["number"])
        for entry in _analysis()["pulls"]
    }
    assert manifest_keys == analysis_keys


def test_no_comment_bodies_or_diffs_are_stored() -> None:
    """The boundary is mechanical: per-PR facts carry counts and paths,
    never free-text bodies or patch content."""
    for entry in _analysis()["pulls"]:
        comments = entry.get("review_comments") or {}
        assert "body" not in json.dumps(comments)
        assert "patch" not in (entry.get("files") or {})


def test_candidate_policies_are_scored_on_discovery_only() -> None:
    analysis = _analysis()
    discovery = {
        (entry["repo"], entry["number"])
        for entry in analysis["pulls"]
        if entry["split"] == "discovery"
    }
    policies = analysis["candidate_policies"]
    for name in (
        "verifier_change_independence", "green_but_not_exercised",
    ):
        policy = policies[name]
        for case in policy["positive_cases"]:
            key = (case["repo"], case["number"])
            assert key in discovery, (
                f"{name}: positive case {key} leaks from the holdout"
            )
        for case in policy["negative_controls"]:
            key = (case["repo"], case["number"])
            assert key in discovery, (
                f"{name}: negative control {key} leaks from the holdout"
            )


def test_every_policy_has_the_full_dod_surface() -> None:
    """DoD: positive cases, negative controls, frequency, and a noise
    assessment — for every candidate policy, favorable or not."""
    policies = _analysis()["candidate_policies"]
    for name in (
        "verifier_change_independence", "green_but_not_exercised",
    ):
        policy = policies[name]
        assert policy["definition"]
        assert isinstance(policy["positive_cases"], list)
        assert isinstance(policy["negative_controls"], list)
        assert policy["negative_controls_total"] >= len(
            policy["negative_controls"]
        )
        frequency = policy["frequency"]
        assert 0 <= frequency["firing"] <= frequency["of"]
        assert "noise" in policy


def test_negative_results_are_kept() -> None:
    negative = _analysis()["candidate_policies"]["negative_results"]
    assert "unretrievable_streams" in negative
    assert "kept deliberately" in negative["note"]


def test_verifier_change_has_positive_and_negative_evidence() -> None:
    """The corpus must actually witness the pain it justifies: at least
    one self-validating case and at least one negative control, from
    more than one repository."""
    policy = _analysis()["candidate_policies"][
        "verifier_change_independence"
    ]
    self_validating = policy["positive_with_self_validating_runs"]
    assert self_validating, "no self-validating case was captured"
    assert policy["negative_controls"], "no negative control captured"
    repos = {case["repo"] for case in self_validating}
    assert len(repos) >= 2, (
        "self-validating cases must span repositories, not one project"
    )
