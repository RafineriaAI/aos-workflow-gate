"""Real-agent benchmark harness (``benchmark-case-v0``).

A benchmark case is a directory of recorded artifacts: a predeclared
task with acceptance criteria and budget, a base state, an
``agent-action-v0`` document, the produced patch, and the gate's
bundle/policy/decision triple. The harness **validates and replays**
recorded cases — it never runs an agent, never applies a patch, and
never executes anything a case declares: there is **no arbitrary
command execution** anywhere in this module (not even fixed
subprocesses; Git ancestry uses the compare API or is reported
unverifiable).

Every check reports one of three results:

- ``ok`` — the property was mechanically verified from the artifacts.
- ``failed`` — the property was checked and does not hold.
- ``unverifiable`` — the property cannot be established from the
  artifacts alone, and the harness says so instead of guessing.

The verified-vs-unverifiable boundary is explicit and first-class:
declared timestamps are checked for internal consistency but their
truth is unverifiable; the operator attestation is recorded prose, not
cryptography; and the harness makes **no patch-authorship claim** — it
verifies that the patch bytes match the declared digest, never that the
agent wrote them.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from . import canonical
from .agent_action import compute_digests, validate_action_document
from .collect import DEFAULT_API_URL, Budget, _request_json, validate_api_url
from .errors import InputError
from .evaluate import evaluate
from .evidence import verify_record
from .policy import load_policy

BENCH_CONTRACT = "benchmark-case-v0"
REPORT_SCHEMA_VERSION = "bench-report-v0"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")

_EVENT_ORDER = ("task_declared", "action_captured", "decision_evaluated")

OK = "ok"
FAILED = "failed"
UNVERIFIABLE = "unverifiable"


def load_case(case_dir: Path) -> dict[str, Any]:
    """Load and structurally validate ``case.json`` from a case directory."""
    case_path = case_dir / "case.json"
    try:
        case = json.loads(case_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise InputError(f"cannot read case {case_path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise InputError(f"{case_path}: invalid JSON: {exc}") from exc
    if not isinstance(case, dict):
        raise InputError(f"{case_path}: must be a JSON object")
    where = str(case_path)
    if case.get("contract") != BENCH_CONTRACT:
        raise InputError(
            f"{where}.contract: must be {BENCH_CONTRACT!r}, "
            f"got {case.get('contract')!r}"
        )
    for field in ("case_id",):
        value = case.get(field)
        if not isinstance(value, str) or not value:
            raise InputError(f"{where}.{field}: must be a non-empty string")

    task = case.get("task")
    if not isinstance(task, dict) or not isinstance(
        task.get("description"), str
    ) or not task["description"]:
        raise InputError(f"{where}.task.description: must be a non-empty string")

    criteria = case.get("acceptance_criteria")
    if not isinstance(criteria, list) or not criteria or not all(
        isinstance(item, str) and item for item in criteria
    ):
        raise InputError(
            f"{where}.acceptance_criteria: must be a non-empty list of "
            "strings (predeclared, not written after the fact)"
        )

    budget = case.get("budget")
    if not isinstance(budget, dict) or not budget:
        raise InputError(f"{where}.budget: must be a non-empty mapping")

    base_state = case.get("base_state")
    if not isinstance(base_state, dict):
        raise InputError(f"{where}.base_state: must be a mapping")
    if not isinstance(base_state.get("repository"), str):
        raise InputError(f"{where}.base_state.repository: must be a string")
    base_sha = base_state.get("base_sha")
    if not isinstance(base_sha, str) or not _SHA_RE.match(base_sha):
        raise InputError(
            f"{where}.base_state.base_sha: must be a 40-char lowercase "
            "hex SHA"
        )

    artifacts = case.get("artifacts")
    if not isinstance(artifacts, dict):
        raise InputError(f"{where}.artifacts: must be a mapping")
    for name in ("action", "patch", "bundle", "policy", "record"):
        value = artifacts.get(name)
        if not isinstance(value, str) or not value:
            raise InputError(
                f"{where}.artifacts.{name}: must be a relative file name"
            )
        if Path(value).is_absolute() or ".." in Path(value).parts:
            raise InputError(
                f"{where}.artifacts.{name}: must stay inside the case "
                "directory"
            )

    bindings = case.get("bindings")
    if not isinstance(bindings, dict):
        raise InputError(f"{where}.bindings: must be a mapping")
    for name in ("action_digest", "patch_digest", "record_digest"):
        value = bindings.get(name)
        if not isinstance(value, str) or not _DIGEST_RE.match(value):
            raise InputError(
                f"{where}.bindings.{name}: must match "
                "sha256:<64 lowercase hex>"
            )

    chronology = case.get("chronology")
    if not isinstance(chronology, list) or not chronology:
        raise InputError(f"{where}.chronology: must be a non-empty list")
    for position, event in enumerate(chronology):
        if (
            not isinstance(event, dict)
            or not isinstance(event.get("event"), str)
            or not isinstance(event.get("at"), str)
        ):
            raise InputError(
                f"{where}.chronology[{position}]: must be "
                '{"event": str, "at": str}'
            )

    attestation = case.get("attestation")
    if not isinstance(attestation, dict) or not isinstance(
        attestation.get("statement"), str
    ) or not attestation["statement"]:
        raise InputError(
            f"{where}.attestation.statement: must be a non-empty string "
            "(operator prose, no cryptographic claim)"
        )
    return case


def _check(name: str, result: str, detail: str) -> dict[str, str]:
    return {"name": name, "result": result, "detail": detail}


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return f"sha256:{digest.hexdigest()}"


def _load_json_artifact(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def fetch_compare_status(
    repository: str,
    base: str,
    head: str,
    *,
    token: str | None,
    api_url: str = DEFAULT_API_URL,
    budget: Budget | None = None,
) -> str:
    """Live ancestry probe: GitHub compare status of ``base...head``."""
    api_url = validate_api_url(api_url)
    budget = budget or Budget()
    parts = repository.rstrip("/").rsplit("/", 2)
    slug = "/".join(parts[-2:]) if len(parts) >= 2 else repository
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = _request_json(
        f"{api_url}/repos/{slug}/compare/{base}...{head}",
        headers,
        timeout=30.0,
        budget=budget,
        capability="compare",
    )
    if not isinstance(payload, dict) or not isinstance(
        payload.get("status"), str
    ):
        raise InputError("compare API response has no status")
    return payload["status"]


def verify_case(
    case_dir: Path,
    *,
    live: bool = False,
    token: str | None = None,
    api_url: str = DEFAULT_API_URL,
) -> dict[str, Any]:
    """Verify one recorded benchmark case; return the check report.

    Offline by default: everything that needs the network is reported
    ``unverifiable`` rather than fetched silently. ``live`` enables the
    Git ancestry probe through the compare API.
    """
    case = load_case(case_dir)
    checks: list[dict[str, str]] = []
    artifacts = case["artifacts"]
    paths = {name: case_dir / value for name, value in artifacts.items()}

    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        checks.append(
            _check(
                "artifact_presence", FAILED,
                "missing artifact file(s): " + ", ".join(sorted(missing)),
            )
        )
        return _report(case, checks)
    checks.append(
        _check(
            "artifact_presence", OK,
            f"all {len(paths)} declared artifacts exist",
        )
    )

    # -- chronology: internal consistency only ---------------------------
    chronology = case["chronology"]
    stamps = {e["event"]: e["at"] for e in chronology}
    ordered = [stamps[name] for name in _EVENT_ORDER if name in stamps]
    if len(ordered) < len(_EVENT_ORDER):
        checks.append(
            _check(
                "chronology_consistent", FAILED,
                "chronology must declare task_declared, action_captured, "
                "and decision_evaluated",
            )
        )
    elif ordered != sorted(ordered) or len(set(ordered)) != len(ordered):
        checks.append(
            _check(
                "chronology_consistent", FAILED,
                "declared timestamps are not strictly increasing in the "
                "order task_declared < action_captured < "
                "decision_evaluated",
            )
        )
    else:
        checks.append(
            _check(
                "chronology_consistent", OK,
                "declared order is internally consistent (task predeclared "
                "before action, action before decision)",
            )
        )
    checks.append(
        _check(
            "chronology_truth", UNVERIFIABLE,
            "timestamps are operator-declared; their truth rests on the "
            "attestation, not on cryptography",
        )
    )

    # -- action document and its binding ---------------------------------
    action_doc = _load_json_artifact(paths["action"])
    try:
        validate_action_document(action_doc, where=str(paths["action"]))
        action_ok = True
        checks.append(
            _check("action_document", OK, "agent-action-v0 structurally valid")
        )
    except InputError as exc:
        action_ok = False
        checks.append(_check("action_document", FAILED, str(exc)))

    if action_ok:
        computed = compute_digests(action_doc)
        if computed["action"] == case["bindings"]["action_digest"]:
            checks.append(
                _check(
                    "action_digest_binding", OK,
                    "recomputed action digest matches the case binding",
                )
            )
        else:
            checks.append(
                _check(
                    "action_digest_binding", FAILED,
                    "recomputed action digest does not match the case "
                    "binding",
                )
            )
        base_state = case["base_state"]
        if (
            action_doc["base_sha"] == base_state["base_sha"]
            and action_doc["repository"] == base_state["repository"]
        ):
            checks.append(
                _check(
                    "action_base_binding", OK,
                    "action is bound to the case's declared base state",
                )
            )
        else:
            checks.append(
                _check(
                    "action_base_binding", FAILED,
                    "action repository/base_sha differ from the case's "
                    "declared base state",
                )
            )

    # -- patch digest (bytes only; authorship is out of scope) -----------
    patch_digest = _file_digest(paths["patch"])
    if patch_digest == case["bindings"]["patch_digest"]:
        checks.append(
            _check(
                "patch_digest_binding", OK,
                "patch bytes match the declared digest",
            )
        )
    else:
        checks.append(
            _check(
                "patch_digest_binding", FAILED,
                "patch bytes do not match the declared digest",
            )
        )
    checks.append(
        _check(
            "patch_authorship", UNVERIFIABLE,
            "no patch-authorship claim: the harness verifies bytes "
            "against the binding, not who or what produced them",
        )
    )

    # -- decision record: self-integrity and offline replay --------------
    record = _load_json_artifact(paths["record"])
    bundle = _load_json_artifact(paths["bundle"])
    if not isinstance(record, dict) or not verify_record(record):
        checks.append(
            _check(
                "record_integrity", FAILED,
                "decision record fails its self-digest check",
            )
        )
    elif record.get("record_digest") != case["bindings"]["record_digest"]:
        checks.append(
            _check(
                "record_integrity", FAILED,
                "record self-digest does not match the case binding",
            )
        )
    else:
        checks.append(
            _check(
                "record_integrity", OK,
                "record self-digest verified and bound to the case",
            )
        )
        if bundle is not None and record.get(
            "input_bundle_digest"
        ) == canonical.digest(bundle):
            checks.append(
                _check(
                    "offline_replay", OK,
                    "record replays against the committed bundle with no "
                    "network",
                )
            )
        else:
            checks.append(
                _check(
                    "offline_replay", FAILED,
                    "record's input_bundle_digest does not match the "
                    "committed bundle",
                )
            )
        checks.append(_policy_binding(paths["policy"], record))
        checks.append(_semantic_replay(bundle, paths["policy"], record))
        if action_ok and isinstance(record.get("subject"), dict):
            subject = record["subject"]
            doc_subject = action_doc["subject"]
            if (
                subject.get("sha") == doc_subject["sha"]
                and subject.get("repository") == doc_subject["repository"]
            ):
                checks.append(
                    _check(
                        "subject_binding", OK,
                        "decision subject equals the action's declared "
                        "subject",
                    )
                )
            else:
                checks.append(
                    _check(
                        "subject_binding", FAILED,
                        "decision subject differs from the action's "
                        "declared subject",
                    )
                )

    # -- Git ancestry -----------------------------------------------------
    if action_ok:
        base_sha = case["base_state"]["base_sha"]
        head_sha = action_doc["subject"]["sha"]
        if head_sha == base_sha:
            checks.append(
                _check(
                    "git_ancestry", OK,
                    "subject equals the base commit (propose-only case)",
                )
            )
        elif live:
            try:
                status = fetch_compare_status(
                    case["base_state"]["repository"], base_sha, head_sha,
                    token=token, api_url=api_url,
                )
                if status in ("ahead", "identical"):
                    checks.append(
                        _check(
                            "git_ancestry", OK,
                            f"compare status '{status}': the base is an "
                            "ancestor of the subject",
                        )
                    )
                else:
                    checks.append(
                        _check(
                            "git_ancestry", FAILED,
                            f"compare status '{status}': the subject does "
                            "not descend from the declared base",
                        )
                    )
            except InputError as exc:
                checks.append(_check("git_ancestry", UNVERIFIABLE, str(exc)))
        else:
            checks.append(
                _check(
                    "git_ancestry", UNVERIFIABLE,
                    "offline run: ancestry needs the live compare API "
                    "(--live) or your own git objects; nothing is assumed",
                )
            )

    if isinstance(case.get("baseline"), dict):
        checks.append(
            _check(
                "github_baseline", UNVERIFIABLE,
                "the GitHub baseline (merge-ready state) is "
                "operator-declared from historical platform state; it "
                "is not mechanically re-verifiable offline",
            )
        )
    checks.append(
        _check(
            "operator_attestation", UNVERIFIABLE,
            "attestation is recorded operator prose "
            f"({case['attestation'].get('operator', 'unnamed')}); no "
            "cryptographic authorship claim is made or implied",
        )
    )
    return _report(case, checks)


def _policy_binding(policy_path: Path, record: dict[str, Any]) -> dict[str, str]:
    """The policy artifact must be the policy the record was built from."""
    try:
        policy = load_policy(policy_path)
    except InputError as exc:
        return _check("policy_binding", FAILED, f"policy artifact: {exc}")
    recorded = record.get("policy")
    recorded_digest = (
        recorded.get("digest") if isinstance(recorded, dict) else None
    )
    if policy.digest == recorded_digest:
        return _check(
            "policy_binding", OK,
            "the policy artifact's content digest matches the record's "
            "policy digest",
        )
    return _check(
        "policy_binding", FAILED,
        "the policy artifact does not digest to the record's policy "
        "digest; the case ships a different policy than the decision "
        "used",
    )


def _semantic_replay(
    bundle: Any, policy_path: Path, record: dict[str, Any]
) -> dict[str, str]:
    """True offline semantic replay: bundle + policy → evaluate → compare.

    Digest checks prove the inputs are the recorded ones; this check
    proves the recorded *decision* is what the current evaluator derives
    from them. Compared fields: verdict, summary, reasons, inputs, and
    subject — everything semantic; the generator version is deliberately
    excluded so records replay across releases.
    """
    if bundle is None:
        return _check(
            "semantic_replay", FAILED, "bundle artifact is not valid JSON"
        )
    try:
        policy = load_policy(policy_path)
    except InputError as exc:
        return _check("semantic_replay", FAILED, f"policy artifact: {exc}")
    decision = evaluate(bundle, policy)
    derived: dict[str, Any] = {
        "verdict": decision.verdict,
        "summary": decision.summary,
        "reasons": [reason.as_dict() for reason in decision.reasons],
        "inputs": decision.inputs,
        "subject": decision.subject.as_dict(),
    }
    for field, value in derived.items():
        if record.get(field) != value:
            return _check(
                "semantic_replay", FAILED,
                f"re-evaluating the committed bundle and policy yields a "
                f"different '{field}' than the committed record",
            )
    return _check(
        "semantic_replay", OK,
        "re-evaluating the committed bundle against the committed policy "
        "reproduces the record's verdict, reasons, inputs, and subject",
    )


def _report(case: dict[str, Any], checks: list[dict[str, str]]) -> dict[str, Any]:
    failed = [c["name"] for c in checks if c["result"] == FAILED]
    unverifiable = [c["name"] for c in checks if c["result"] == UNVERIFIABLE]
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "case_id": case["case_id"],
        "checks": checks,
        "verified": [c["name"] for c in checks if c["result"] == OK],
        "failed": failed,
        "unverifiable": unverifiable,
        "ok": not failed,
        "boundary": (
            "the harness validates recorded artifacts and replays the "
            "decision offline; it runs no agent, applies no patch, "
            "executes no command, and makes no claim beyond the checks "
            "listed as verified"
        ),
    }


def render_bench_report(report: dict[str, Any]) -> str:
    """Human-readable rendering of a case verification report."""
    lines = [
        f"case {report['case_id']}: "
        + ("all checks hold" if report["ok"] else "FAILED checks present")
    ]
    for check in report["checks"]:
        lines.append(
            f"  [{check['result']:>12}] {check['name']}: {check['detail']}"
        )
    lines.append("")
    lines.append(f"Boundary: {report['boundary']}.")
    return "\n".join(lines) + "\n"
