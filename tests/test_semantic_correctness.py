"""GitHub semantic, scope, and freshness correctness (dual-track).

Contract tests for the requirement classification: GitHub's own
required-status-check semantics (neutral/skipped pass) are recorded per
control as ``github_equivalent`` next to the gate's stricter evidence
``state``; rulesets and classic protection are unioned, never chosen;
merge_group subjects resolve to the queue's head and base branch; and a
collection that did not end ``complete`` can never yield a plain PASS.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from aos_workflow_gate import cli
from aos_workflow_gate.collect import (
    Budget,
    _merge_queue_base,
    build_generated_policy,
    resolve_github_context,
)
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.policy import Policy
from aos_workflow_gate.requirements import (
    classify_control,
    github_baseline,
    merge_protection_controls,
    protection_digest,
)

SHA = "c" * 40
APP = 15368


def _run(
    name: str,
    conclusion: str | None = "success",
    *,
    app_id: int | None = APP,
    status: str = "completed",
) -> dict[str, Any]:
    run: dict[str, Any] = {
        "id": 1,
        "name": name,
        "head_sha": SHA,
        "status": status,
        "conclusion": conclusion,
        "completed_at": "2026-07-10T00:00:00Z",
        "details_url": "https://github.com/octo/repo/actions/runs/111/job/9",
    }
    if app_id is not None:
        run["app"] = {"id": app_id}
    return run


CONTROL = {"context": "ci", "integration_id": None}


# --- dual-track classification ------------------------------------------


@pytest.mark.parametrize(
    "conclusion,state,equivalent",
    [
        ("success", "satisfied", "would_pass"),
        ("neutral", "failed", "would_pass"),
        ("skipped", "failed", "would_pass"),
        ("failure", "failed", "would_fail"),
        ("cancelled", "failed", "would_fail"),
        ("timed_out", "failed", "would_fail"),
        ("action_required", "failed", "would_fail"),
    ],
)
def test_conclusion_dual_track(
    conclusion: str, state: str, equivalent: str
) -> None:
    classified = classify_control(CONTROL, [_run("ci", conclusion)], [])
    assert classified["state"] == state
    assert classified["github_equivalent"] == equivalent
    # the raw conclusion is never lost to normalization
    assert classified["observed"]["conclusion"] == conclusion


def test_pending_and_missing_would_wait() -> None:
    pending = classify_control(
        CONTROL, [_run("ci", None, status="in_progress")], []
    )
    assert pending["state"] == "pending"
    assert pending["github_equivalent"] == "would_wait"

    missing = classify_control(CONTROL, [], [])
    assert missing["state"] == "missing"
    # GitHub shows an absent required context as "Expected" and waits
    assert missing["github_equivalent"] == "would_wait"


def test_imposter_app_would_wait_and_unreadable_is_unknown() -> None:
    bound = {"context": "ci", "integration_id": APP}
    imposter = classify_control(bound, [_run("ci", app_id=666)], [])
    assert imposter["state"] == "unverifiable"
    assert imposter["github_equivalent"] == "would_wait"

    unreadable = classify_control(CONTROL, [], [], statuses_readable=False)
    assert unreadable["state"] == "unverifiable"
    assert unreadable["github_equivalent"] == "unknown"


def test_legacy_status_dual_track() -> None:
    ok = classify_control(
        CONTROL, [], [{"context": "ci", "state": "success"}]
    )
    assert (ok["state"], ok["github_equivalent"]) == (
        "satisfied", "would_pass"
    )
    err = classify_control(
        CONTROL, [], [{"context": "ci", "state": "error"}]
    )
    assert (err["state"], err["github_equivalent"]) == (
        "failed", "would_fail"
    )


def test_github_baseline_precedence() -> None:
    def control(equivalent: str) -> dict[str, Any]:
        return {"context": "x", "github_equivalent": equivalent}

    assert github_baseline([]) == "no_required_checks"
    assert github_baseline([control("would_pass")]) == "clear"
    assert github_baseline(
        [control("would_pass"), control("would_wait")]
    ) == "waiting"
    assert github_baseline(
        [control("would_wait"), control("unknown")]
    ) == "unknown"
    assert github_baseline(
        [control("unknown"), control("would_fail")]
    ) == "blocked"


# --- rulesets + classic protection union --------------------------------


def test_merge_protection_controls_union() -> None:
    merged = merge_protection_controls(
        [
            {"context": "ci", "integration_id": None},
            {"context": "lint", "integration_id": APP},
            {"context": "shared", "integration_id": APP},
        ],
        [
            {"context": "ci", "integration_id": APP},
            {"context": "legacy", "integration_id": None},
            {"context": "shared", "integration_id": APP},
        ],
    )
    by_identity = {
        (control["context"], control["integration_id"]): control
        for control in merged
    }
    assert set(by_identity) == {
        ("ci", None), ("ci", APP), ("lint", APP), ("legacy", None),
        ("shared", APP),
    }
    # Same context with a different app binding remains a separate control.
    assert by_identity[("ci", None)]["required_by"] == ["rulesets"]
    assert by_identity[("ci", APP)]["required_by"] == [
        "classic_branch_protection"
    ]
    assert by_identity[("ci", None)]["source_id"] != (
        by_identity[("ci", APP)]["source_id"]
    )
    # Only an identical tuple merges deterministic provenance.
    assert by_identity[("shared", APP)]["required_by"] == [
        "rulesets", "classic_branch_protection",
    ]
    assert by_identity[("shared", APP)]["source_id"] == "shared"
    digest_a = protection_digest(merged, strict=False)
    assert digest_a != protection_digest(merged, strict=True)
    assert digest_a != protection_digest(merged[:2], strict=False)


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
            "required_status_checks": [{"context": "ci", "integration_id": APP}]
        },
    }
]

CLASSIC_BRANCH = {
    "protected": True,
    "protection": {
        "required_status_checks": {
            "strict": True,
            "checks": [{"context": "legacy-ci", "app_id": 1}],
        }
    },
}


def _install(
    monkeypatch: pytest.MonkeyPatch,
    *,
    rules: Any,
    runs: list[dict[str, Any]],
    branch_payload: Any = None,
) -> None:
    from aos_workflow_gate import collect as collect_module

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        if "/rules/branches/" in url:
            return _FakeResponse(rules)
        if "/branches/" in url:
            return _FakeResponse(branch_payload or {"protected": False})
        if url.endswith("/status") or "/status?" in url:
            return _FakeResponse({"state": "success", "statuses": []})
        return _FakeResponse({"total_count": len(runs), "check_runs": runs})

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_NAME", raising=False)
    monkeypatch.delenv("GITHUB_API_URL", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)


def _run_gate(tmp_path: Path) -> tuple[int, dict[str, Any], dict[str, Any]]:
    rc = cli.main(
        ["run", "--github-context",
         "--wait-seconds", "0.01",
         "--poll-interval", "0.01",
         "--out", str(tmp_path / "record.json"),
         "--bundle-out", str(tmp_path / "bundle.json"),
         "--policy-out", str(tmp_path / "policy.json")]
    )
    record = json.loads((tmp_path / "record.json").read_text("utf-8"))
    bundle = json.loads((tmp_path / "bundle.json").read_text("utf-8"))
    return rc, record, bundle


def test_discovery_unions_rulesets_and_classic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(
        monkeypatch,
        rules=RULES,
        runs=[_run("ci"), _run("legacy-ci", app_id=1)],
        branch_payload=CLASSIC_BRANCH,
    )
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    assert record["verdict"] == "PASS"
    collection = bundle["collection"]
    assert collection["protection_source"] == (
        "rulesets+classic_branch_protection"
    )
    requirements = {
        req["context"]: req for req in collection["requirements"]
    }
    assert set(requirements) == {"ci", "legacy-ci"}
    assert requirements["ci"]["required_by"] == ["rulesets"]
    assert requirements["legacy-ci"]["required_by"] == [
        "classic_branch_protection"
    ]
    assert requirements["legacy-ci"]["integration_id"] == 1
    assert collection["github_baseline"] == "clear"
    assert collection["protection_digest"].startswith("sha256:")
    by_id = {source["id"]: source for source in bundle["sources"]}
    assert by_id["legacy-ci"]["required"] is True


def test_same_context_different_apps_cannot_collapse_to_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rules = [
        {
            "type": "required_status_checks",
            "parameters": {
                "required_status_checks": [
                    {"context": "ci", "integration_id": APP},
                    {"context": "ci", "integration_id": 99999},
                ]
            },
        }
    ]
    _install(monkeypatch, rules=rules, runs=[_run("ci", app_id=APP)])
    rc, record, bundle = _run_gate(tmp_path)

    assert rc == 0
    assert record["verdict"] == "BLOCK"
    requirements = bundle["collection"]["requirements"]
    by_app = {
        item["integration_id"]: item
        for item in requirements
    }
    assert by_app[APP]["state"] == "satisfied"
    assert by_app[99999]["state"] == "unverifiable"
    assert by_app[APP]["source_id"] != by_app[99999]["source_id"]

    required_sources = {
        source["id"]: source
        for source in bundle["sources"]
        if source["required"]
    }
    assert set(required_sources) == {by_app[APP]["source_id"]}
    missing = next(
        reason for reason in record["reasons"]
        if reason["rule"] == "missing_required_source"
    )
    assert missing["source_id"] == by_app[99999]["source_id"]
    assert "unverifiable" in missing["detail"]


def test_observation_is_bound_to_exact_head_sha(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    wrong_subject_run = _run("ci")
    wrong_subject_run["head_sha"] = "f" * 40
    _install(monkeypatch, rules=RULES, runs=[wrong_subject_run])

    rc, record, bundle = _run_gate(tmp_path)

    assert rc == 0
    assert record["verdict"] == "BLOCK"
    collection = bundle["collection"]
    assert collection["status"] == "subject_mismatch"
    assert collection["observation_scope"] == {
        "repository": "octo/repo",
        "head_sha": SHA,
    }
    assert collection["subject_mismatch_runs"] == [1]
    assert not any(source["id"] == "ci" for source in bundle["sources"])


def test_skipped_required_diverges_from_github_baseline(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The contrast case: GitHub would merge (skipped passes there); the
    gate fails the evidence and records the divergence per control."""
    _install(monkeypatch, rules=RULES, runs=[_run("ci", "skipped")])
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    assert record["verdict"] == "BLOCK"
    requirement = bundle["collection"]["requirements"][0]
    assert requirement["state"] == "failed"
    assert requirement["github_equivalent"] == "would_pass"
    assert bundle["collection"]["github_baseline"] == "clear"


# --- merge_group subject resolution --------------------------------------


def test_merge_queue_ref_parse() -> None:
    assert _merge_queue_base(
        "gh-readonly-queue/main/pr-7-0a1b2c3d"
    ) == "main"
    assert _merge_queue_base(
        "gh-readonly-queue/release/v1/pr-9-abc"
    ) == "release/v1"
    assert _merge_queue_base("feature/pr-branch") is None


def test_merge_group_context_resolution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = "d" * 40
    event = {
        "merge_group": {
            "head_sha": head,
            "base_ref": "refs/heads/main",
            "head_ref": "refs/heads/gh-readonly-queue/main/pr-7-abc",
        }
    }
    event_path = tmp_path / "event.json"
    event_path.write_text(json.dumps(event), encoding="utf-8")
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_SHA", "e" * 40)
    monkeypatch.setenv("GITHUB_REF", "refs/heads/gh-readonly-queue/main/pr-7-abc")
    monkeypatch.setenv("GITHUB_REF_NAME", "gh-readonly-queue/main/pr-7-abc")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "merge_group")
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_path))
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    context = resolve_github_context()
    assert context["sha"] == head
    assert context["branch"] == "main"
    assert context["event_name"] == "merge_group"


def test_merge_queue_branch_from_ref_name_without_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("GITHUB_REF_NAME", "gh-readonly-queue/main/pr-3-abc")
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    assert resolve_github_context()["branch"] == "main"


# --- no PASS on unknown/incomplete collections ----------------------------


def _policy(**rules: str) -> Policy:
    base = {
        "missing_required_source": "BLOCK",
        "failed_required_source": "BLOCK",
        "malformed_input": "BLOCK",
        "advisory_warning": "WARN",
    }
    base.update(rules)
    return Policy.from_dict(
        {
            "policy_id": "test",
            "rules": base,
            "required_sources": ["ci"],
        }
    )


def _bundle(status: str | None) -> dict[str, Any]:
    bundle: dict[str, Any] = {
        "schema_version": "draft-0",
        "subject": {"repository": "octo/repo", "sha": SHA},
        "sources": [
            {
                "id": "ci",
                "kind": "github_check",
                "status": "success",
                "required": True,
            }
        ],
    }
    if status is not None:
        bundle["collection"] = {"status": status}
    return bundle


@pytest.mark.parametrize("status", ["truncated", "wait_timeout", "weird"])
def test_incomplete_collection_never_passes(status: str) -> None:
    decision = evaluate(_bundle(status), _policy())
    assert decision.verdict == "WARN"
    reason = next(
        item
        for item in decision.reasons
        if item.rule == "incomplete_collection"
    )
    assert reason.state == status
    assert reason.as_dict()["state"] == status


def test_complete_or_unrecorded_collection_passes() -> None:
    assert evaluate(_bundle("complete"), _policy()).verdict == "PASS"
    assert evaluate(_bundle(None), _policy()).verdict == "PASS"


def test_incomplete_collection_severity_is_policy_owned() -> None:
    blocking = _policy(incomplete_collection="BLOCK")
    assert evaluate(_bundle("truncated"), blocking).verdict == "BLOCK"


def test_generated_policy_carries_incomplete_collection_rule() -> None:
    policy = build_generated_policy(_bundle("complete"), required=["ci"])
    assert policy["rules"]["incomplete_collection"] == "WARN"


def test_collect_records_observed_at(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install(monkeypatch, rules=[], runs=[_run("ci")])
    out = tmp_path / "bundle.json"
    rc = cli.main(
        ["collect", "--repository", "octo/repo", "--sha", SHA,
         "--out", str(out)]
    )
    assert rc == 0
    bundle = json.loads(out.read_text("utf-8"))
    observed = bundle["collection"]["observed_at"]
    assert len(observed) == 20 and observed.endswith("Z")
    assert observed[4] == "-" and observed[10] == "T"


# --- pagination and API-error fail-closed ---------------------------------


def test_branch_rules_pagination(monkeypatch: pytest.MonkeyPatch) -> None:
    from aos_workflow_gate import collect as collect_module
    from aos_workflow_gate.checkpr import fetch_branch_rules

    pages = {
        1: [{"type": "required_status_checks", "parameters": {}}] * 100,
        2: [{"type": "deletion"}],
    }

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        page = int(request.full_url.rsplit("page=", 1)[1])
        return _FakeResponse(pages.get(page, []))

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    rules = fetch_branch_rules(
        "https://api.github.com", "octo/repo", "main",
        token=None, budget=Budget(),
    )
    assert len(rules) == 101


def test_unreadable_classic_protection_degrades_with_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rulesets stay authoritative when the classic surface errors; the
    degradation is recorded, never silent, and never a verdict."""
    import io
    from email.message import Message
    from urllib.error import HTTPError

    from aos_workflow_gate import collect as collect_module

    runs = [_run("ci")]

    def opener(request: Any, timeout: float | None = None) -> _FakeResponse:
        url = request.full_url
        if "/rules/branches/" in url:
            return _FakeResponse(RULES)
        if "/branches/" in url:
            raise HTTPError(url, 403, "forbidden", Message(), io.BytesIO(b""))
        if url.endswith("/status") or "/status?" in url:
            return _FakeResponse({"state": "success", "statuses": []})
        return _FakeResponse({"total_count": len(runs), "check_runs": runs})

    monkeypatch.setattr(collect_module.urllib.request, "urlopen", opener)
    monkeypatch.setenv("GITHUB_REPOSITORY", "octo/repo")
    monkeypatch.setenv("GITHUB_SHA", SHA)
    monkeypatch.setenv("GITHUB_REF_NAME", "main")
    monkeypatch.delenv("GITHUB_BASE_REF", raising=False)
    monkeypatch.delenv("GITHUB_SERVER_URL", raising=False)
    monkeypatch.delenv("GITHUB_EVENT_PATH", raising=False)
    monkeypatch.delenv("GITHUB_RUN_ID", raising=False)
    rc, record, bundle = _run_gate(tmp_path)
    assert rc == 0
    assert record["verdict"] == "PASS"
    assert bundle["collection"]["protection_source"] == "rulesets"
    assert "could not be read" in bundle["collection"][
        "classic_protection_note"
    ]
