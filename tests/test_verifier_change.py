"""Trusted verifier-change policy: self-validating changes are named.

Pins the mechanical determination (no model output in any verdict
path): path classification, the solely-vs-independently distinction via
check-suite ids, fail-closed collection, and acknowledgement as
recorded evidence, the advisory-by-default severity, and — the DoD —
that the detector fires on the frozen corpus's real Airflow and Celery
self-validating pull requests.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate import verifier_change as verifier_change_module
from aos_workflow_gate.collect import Budget
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.policy import Policy
from aos_workflow_gate.verifier_change import (
    analyze_verifier_change,
    classify_verifier_paths,
    fetch_pr_files,
    is_routine_bump,
)

ROOT = Path(__file__).resolve().parents[1]
SHA = "c" * 40
BASE = "b" * 40
APP = 15368


# --- path classification ----------------------------------------------------


def test_classify_verifier_paths() -> None:
    buckets = classify_verifier_paths(
        [
            ".github/workflows/ci.yml",
            "tests/test_x.py",
            "conftest.py",
            ".pre-commit-config.yaml",
            "policies/default.yml",
            "requirements-dev.txt",
            "pyproject.toml",
            "src/app.py",
        ]
    )
    assert buckets["workflow"] == [".github/workflows/ci.yml"]
    assert buckets["test_harness"] == ["conftest.py"]
    assert buckets["test_cases"] == ["tests/test_x.py"]
    assert buckets["scanner_config"] == [".pre-commit-config.yaml"]
    assert buckets["policy"] == ["policies/default.yml"]
    assert buckets["dependency_pins"] == ["requirements-dev.txt"]
    assert buckets["packaging"] == ["pyproject.toml"]
    assert buckets["other"] == ["src/app.py"]


def test_operator_policy_path_counts_as_policy() -> None:
    buckets = classify_verifier_paths(
        ["gates/my-gate.yml"], extra_policy_paths=["gates/my-gate.yml"]
    )
    assert buckets["policy"] == ["gates/my-gate.yml"]


# --- routine-bump exclusion ---------------------------------------------------


def test_routine_bump_requires_bot_and_pin_only_delta() -> None:
    pins_only = classify_verifier_paths(
        ["requirements.txt", "pyproject.toml"]
    )
    assert is_routine_bump(pins_only, bot_author=True) is True
    assert is_routine_bump(pins_only, bot_author=False) is False
    with_code = classify_verifier_paths(["requirements.txt", "src/x.py"])
    assert is_routine_bump(with_code, bot_author=True) is False
    with_test = classify_verifier_paths([
        "requirements.txt", "tests/test_dependency.py"
    ])
    assert is_routine_bump(with_test, bot_author=True) is False
    with_workflow = classify_verifier_paths(
        ["requirements.txt", ".github/workflows/ci.yml"]
    )
    assert is_routine_bump(with_workflow, bot_author=True) is False


# --- the core determination ---------------------------------------------------


def _wrun(path: str, suite_id: int) -> dict[str, Any]:
    return {"id": suite_id * 10, "path": path, "check_suite_id": suite_id}


def _crun(name: str, suite_id: int) -> dict[str, Any]:
    return {"name": name, "check_suite": {"id": suite_id}}


def test_solely_changed_mechanism_is_not_independent() -> None:
    analysis = analyze_verifier_change(
        [".github/workflows/ci.yml", "src/app.py"],
        [_wrun(".github/workflows/ci.yml", 1)],
        [_crun("ci / validate", 1), _crun("ci / lint", 1)],
    )
    assert analysis["verifier_change"] is True
    assert analysis["self_validating_workflows"] == [
        ".github/workflows/ci.yml"
    ]
    assert analysis["non_independent_sources"] == [
        "ci / lint", "ci / validate",
    ]
    assert analysis["unchanged_workflow_runs"] == 0
    assert "no model output" in analysis["note"]


def test_unchanged_workflow_is_only_a_candidate_alternative() -> None:
    analysis = analyze_verifier_change(
        [".github/workflows/ci.yml"],
        [
            _wrun(".github/workflows/ci.yml", 1),
            _wrun(".github/workflows/security.yml", 2),
        ],
        [_crun("ci / validate", 1), _crun("security-scan", 2)],
    )
    # only the changed workflow's evidence is classified non-independent
    assert analysis["non_independent_sources"] == ["ci / validate"]
    assert analysis["unchanged_workflow_runs"] == 1


def test_no_verifier_change_flags_nothing() -> None:
    analysis = analyze_verifier_change(
        ["src/app.py", "README.md"],
        [_wrun(".github/workflows/ci.yml", 1)],
        [_crun("ci / validate", 1)],
    )
    assert analysis["verifier_change"] is False
    assert analysis["non_independent_sources"] == []


def test_acknowledgement_is_recorded_evidence() -> None:
    analysis = analyze_verifier_change(
        [".github/workflows/ci.yml"],
        [_wrun(".github/workflows/ci.yml", 1)],
        [_crun("ci / validate", 1)],
        acknowledged="reviewed by release manager",
    )
    assert analysis["acknowledged"] == "reviewed by release manager"
    # affected sources stay visible under acknowledgement
    assert analysis["non_independent_sources"] == ["ci / validate"]


# --- reason emission: advisory by default, policy-tunable ---------------------


def _policy(**extra_rules: str) -> Policy:
    rules = {
        "missing_required_source": "BLOCK",
        "failed_required_source": "BLOCK",
        "malformed_input": "BLOCK",
        "advisory_warning": "WARN",
    }
    rules.update(extra_rules)
    return Policy.from_dict(
        {"policy_id": "test", "rules": rules, "required_sources": ["ci"]}
    )


def _bundle(verifier: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "draft-0",
        "subject": {"repository": "octo/repo", "sha": SHA},
        "sources": [
            {
                "id": "ci", "kind": "github_check", "status": "success",
                "required": True,
            }
        ],
        "collection": {"status": "complete", "verifier_change": verifier},
    }


def _flagged(**overrides: Any) -> dict[str, Any]:
    verifier: dict[str, Any] = {
        "analyzed": True,
        "verifier_change": True,
        "routine_bump_excluded": False,
        "non_independent_sources": ["ci"],
        "unchanged_workflow_runs": 0,
    }
    verifier.update(overrides)
    return verifier


def test_default_is_advisory_warn_never_block() -> None:
    decision = evaluate(_bundle(_flagged()), _policy())
    assert decision.verdict == "WARN"
    reason = next(
        r for r in decision.reasons
        if r.rule == "non_independent_evidence"
    )
    assert "grades itself" in reason.detail
    assert "governed outside" in reason.detail


def test_policy_can_raise_to_block_or_silence() -> None:
    blocking = _policy(non_independent_evidence="BLOCK")
    assert evaluate(_bundle(_flagged()), blocking).verdict == "BLOCK"
    silenced = _policy(non_independent_evidence="PASS")
    assert evaluate(_bundle(_flagged()), silenced).verdict == "PASS"


def test_unrelated_self_validation_stays_evidence_only() -> None:
    policy = Policy.from_dict(
        {
            "policy_id": "test",
            "rules": {
                "missing_required_source": "BLOCK",
                "failed_required_source": "BLOCK",
                "malformed_input": "BLOCK",
                "advisory_warning": "PASS",
                "no_required_sources": "PASS",
                "non_independent_evidence": "WARN",
            },
            "required_sources": ["ci"],
        }
    )

    decision = evaluate(
        _bundle(_flagged(non_independent_sources=["unrelated"])), policy
    )

    assert decision.verdict == "PASS"
    assert not any(
        reason.rule == "non_independent_evidence"
        for reason in decision.reasons
    )


def test_acknowledgement_does_not_suppress_the_reason() -> None:
    acknowledged = _flagged(acknowledged="reviewed")
    decision = evaluate(_bundle(acknowledged), _policy())
    assert decision.verdict == "WARN"
    reason = next(
        r for r in decision.reasons
        if r.rule == "non_independent_evidence"
    )
    assert "does not authorize" in reason.detail


def test_recorded_routine_pin_bump_stays_quiet() -> None:
    bump = _flagged(routine_bump_excluded=True)
    assert evaluate(_bundle(bump), _policy()).verdict == "PASS"


def test_unchanged_workflow_does_not_claim_independence() -> None:
    decision = evaluate(
        _bundle(_flagged(unchanged_workflow_runs=2)), _policy()
    )
    reason = next(
        r for r in decision.reasons
        if r.rule == "non_independent_evidence"
    )
    assert "governed outside" in reason.detail


# --- end to end through check-pr ----------------------------------------------


class _FakeResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


RULES = [
    {
        "type": "required_status_checks",
        "parameters": {
            "required_status_checks": [
                {"context": "ci / validate", "integration_id": APP}
            ]
        },
    }
]


def _install_check_pr(monkeypatch: pytest.MonkeyPatch) -> None:
    from aos_workflow_gate import collect as collect_module

    check_run = {
        "id": 1,
        "name": "ci / validate",
        "head_sha": SHA,
        "status": "completed",
        "conclusion": "success",
        "completed_at": "2026-07-10T00:00:00Z",
        "app": {"id": APP},
        "check_suite": {"id": 77},
    }

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        if "/files" in url:
            return _FakeResponse(
                [{"filename": ".github/workflows/ci.yml"},
                 {"filename": "src/app.py"}]
            )
        if "/pulls/" in url:
            return _FakeResponse(
                {
                    "head": {"sha": SHA, "repo": {"full_name": "octo/repo"}},
                    "base": {
                        "ref": "main",
                        "sha": BASE,
                        "repo": {"full_name": "octo/repo"},
                    },
                    "state": "open",
                    "merged": False,
                    "draft": False,
                    "user": {"type": "User"},
                }
            )
        if "/rules/branches/" in url:
            return _FakeResponse(RULES)
        if "/check-suites" in url:
            return _FakeResponse({"total_count": 0, "check_suites": []})
        if "/actions/runs" in url:
            return _FakeResponse(
                {
                    "total_count": 1,
                    "workflow_runs": [
                        {
                            "id": 5,
                            "path": ".github/workflows/ci.yml",
                            "check_suite_id": 77,
                            "head_sha": SHA,
                            "status": "completed",
                            "conclusion": "success",
                        }
                    ],
                }
            )
        if "/branches/" in url:
            return _FakeResponse({"protected": False})
        if url.endswith("/status") or "/status?" in url:
            return _FakeResponse({"state": "success", "statuses": []})
        return _FakeResponse({"total_count": 1, "check_runs": [check_run]})

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)


def test_check_pr_flags_self_validating_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _install_check_pr(monkeypatch)
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["check-pr", "https://github.com/octo/repo/pull/42"])
    assert rc == 0  # advisory: never fails the process
    record = json.loads((tmp_path / "gate-decision.json").read_text("utf-8"))
    assert record["verdict"] == "WARN"
    rules_hit = {reason["rule"] for reason in record["reasons"]}
    assert "non_independent_evidence" in rules_hit
    bundle = json.loads(
        (tmp_path / ".aos-gate" / "bundle.json").read_text("utf-8")
    )
    verifier = bundle["collection"]["verifier_change"]
    assert verifier["non_independent_sources"] == ["ci / validate"]
    assert record["observation"]["verifier_change"] == {
        "available": True,
        "non_independent_sources": 1,
        "routine_bump_excluded": False,
        "acknowledged": False,
    }
    assert "grades itself" not in capsys.readouterr().err


def test_check_pr_acknowledgement_records_without_suppressing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_check_pr(monkeypatch)
    monkeypatch.chdir(tmp_path)
    rc = cli.main(
        ["check-pr", "https://github.com/octo/repo/pull/42",
         "--acknowledge-verifier-change",
         "release manager reviewed the diff"]
    )
    assert rc == 0
    record = json.loads((tmp_path / "gate-decision.json").read_text("utf-8"))
    rules_hit = {reason["rule"] for reason in record["reasons"]}
    assert "non_independent_evidence" in rules_hit
    bundle = json.loads(
        (tmp_path / ".aos-gate" / "bundle.json").read_text("utf-8")
    )
    verifier = bundle["collection"]["verifier_change"]
    assert verifier["acknowledged"] == "release manager reviewed the diff"
    assert verifier["non_independent_sources"] == ["ci / validate"]


# --- DoD: the frozen corpus's real Airflow/Celery cases ------------------------


def test_detector_fires_on_frozen_airflow_and_celery_cases() -> None:
    """Replay the detector over the frozen discovery corpus: every
    recorded self-validating PR (real Airflow/Celery/self history) must
    fire, and the corpus's negative controls must not."""
    analysis = json.loads(
        (ROOT / "benchmarks" / "discovery" / "analysis.json").read_text(
            encoding="utf-8"
        )
    )
    by_key = {
        (entry["repo"], entry["number"]): entry
        for entry in analysis["pulls"]
    }
    policy = analysis["candidate_policies"]["verifier_change_independence"]
    positives = policy["positive_with_self_validating_runs"]
    repos = {case["repo"] for case in positives}
    assert {"apache/airflow", "celery/celery"} <= repos

    for case in positives:
        entry = by_key[(case["repo"], case["number"])]
        changed = list(entry["files"]["workflow"])
        runs = [
            {"path": path, "check_suite_id": 1}
            for path in entry["workflow_runs"]["self_validating_paths"]
        ]
        result = analyze_verifier_change(changed, runs, [])
        assert result["self_validating_workflows"], (
            f"detector missed frozen case {case['repo']}#{case['number']}"
        )

    for case in policy["negative_controls"]:
        entry = by_key[(case["repo"], case["number"])]
        files = entry.get("files") or {}
        if not files.get("retrievable"):
            continue
        changed = list(files.get("workflow") or [])
        result = analyze_verifier_change(changed, [], [])
        assert not result["verifier_change"] or not changed, (
            f"negative control {case['repo']}#{case['number']} "
            "unexpectedly produced self-validating evidence"
        )


def test_unavailable_analysis_is_policy_visible() -> None:
    unavailable = {
        "analyzed": False,
        "available": False,
        "unavailable": "AOS-PERM-004 Actions API is unreadable",
    }
    decision = evaluate(_bundle(unavailable), _policy())
    assert decision.verdict == "WARN"
    reason = next(
        r for r in decision.reasons
        if r.rule == "verifier_change_unavailable"
    )
    assert "AOS-PERM-004" in reason.detail

    blocking = _policy(verifier_change_unavailable="BLOCK")
    assert evaluate(_bundle(unavailable), blocking).verdict == "BLOCK"


def test_pr_file_collection_keeps_renames_and_reports_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def request(*args: Any, **kwargs: Any) -> list[dict[str, str]]:
        nonlocal calls
        calls += 1
        return [
            {
                "filename": f"new/{calls}-{index}.yml",
                "previous_filename": f"old/{calls}-{index}.yml",
            }
            for index in range(100)
        ]

    monkeypatch.setattr(verifier_change_module, "_request_json", request)
    paths, truncated = fetch_pr_files(
        "https://api.github.com",
        "octo/repo",
        42,
        token=None,
        budget=Budget(max_api_calls=40),
    )
    assert truncated is True
    assert calls == 30
    assert len(paths) == 6000
    assert "old/1-0.yml" in paths
    assert "new/30-99.yml" in paths


def test_frozen_policy_is_opened_once_on_holdout() -> None:
    analysis = json.loads(
        (ROOT / "benchmarks" / "discovery" / "analysis.json").read_text(
            encoding="utf-8"
        )
    )
    holdout = [entry for entry in analysis["pulls"] if entry["split"] == "holdout"]
    assert len(holdout) == 20

    flagged: list[tuple[str, int]] = []
    for entry in holdout:
        changed = list(entry["files"]["workflow"])
        runs = [
            {"path": path, "check_suite_id": index}
            for index, path in enumerate(
                entry["workflow_runs"]["self_validating_paths"], start=1
            )
        ]
        check_runs = [
            {"name": f"recorded-suite-{index}", "check_suite": {"id": index}}
            for index in range(1, len(runs) + 1)
        ]
        result = analyze_verifier_change(
            changed,
            runs,
            check_runs,
            bot_author=bool(entry["author"]["bot"]),
        )
        if result["non_independent_sources"]:
            flagged.append((entry["repo"], entry["number"]))

    assert flagged == [("celery/celery", 10362)]

def _pr_meta(*, head: str = SHA, base: str = BASE) -> dict[str, Any]:
    return {
        "head_sha": head,
        "base_sha": base,
        "base_ref": "main",
        "author_bot": False,
    }


def test_collector_rejects_head_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    metadata = iter([_pr_meta(), _pr_meta(head="d" * 40)])
    monkeypatch.setattr(cli, "fetch_pr", lambda *args, **kwargs: next(metadata))
    monkeypatch.setattr(
        cli,
        "fetch_pr_files",
        lambda *args, **kwargs: ([".github/workflows/ci.yml"], False),
    )
    monkeypatch.setattr(
        cli,
        "fetch_workflow_runs",
        lambda *args, **kwargs: ([_wrun(".github/workflows/ci.yml", 1)], False),
    )

    result = cli._collect_verifier_change(
        repository="octo/repo",
        sha=SHA,
        pr_number=42,
        check_runs=[_crun("ci", 1)],
        token=None,
        api_url="https://api.github.com",
        budget=Budget(),
        acknowledged=None,
        expected_base_sha=BASE,
    )
    assert result["analyzed"] is False
    assert "changed during" in result["unavailable"]


def test_collector_rejects_truncated_file_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli, "fetch_pr", lambda *args, **kwargs: _pr_meta())
    monkeypatch.setattr(
        cli,
        "fetch_pr_files",
        lambda *args, **kwargs: ([".github/workflows/ci.yml"], True),
    )

    result = cli._collect_verifier_change(
        repository="octo/repo",
        sha=SHA,
        pr_number=42,
        check_runs=[],
        token=None,
        api_url="https://api.github.com",
        budget=Budget(),
        acknowledged=None,
        expected_base_sha=BASE,
    )
    assert result["analyzed"] is False
    assert "3,000-file" in result["unavailable"]