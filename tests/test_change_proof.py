from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from aos_workflow_gate import canonical, cli
from aos_workflow_gate.change_proof import (
    CONFIRMED_FAILURE,
    INCONCLUSIVE,
    NOT_DISTINGUISHED,
    SUCCESS,
    build_bundle,
    prove_change,
)
from aos_workflow_gate.errors import InputError
from aos_workflow_gate.evaluate import evaluate
from aos_workflow_gate.policy import load_policy
from aos_workflow_gate.source_contract import validate_source_v0
from aos_workflow_gate.summarize import diagnose

ROOT = Path(__file__).resolve().parents[1]


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout.strip()


def _write(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8", newline="\n")


def _commit(repo: Path, message: str) -> str:
    _git(repo, "add", "--all")
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


def _repository(tmp_path: Path, *, head_expectation: int) -> tuple[Path, str, str]:
    repo = tmp_path / "subject"
    repo.mkdir()
    _git(repo, "init", "--initial-branch=main")
    _git(repo, "config", "user.name", "AOS Test")
    _git(repo, "config", "user.email", "test@example.invalid")
    _write(repo, "app.py", "def value():\n    return 1\n")
    _write(
        repo,
        "tests/check.py",
        "from app import value\nassert value() == 1\n",
    )
    base_sha = _commit(repo, "base")

    _write(repo, "app.py", "def value():\n    return 2\n")
    _write(
        repo,
        "tests/check.py",
        f"from app import value\nassert value() == {head_expectation}\n",
    )
    head_sha = _commit(repo, "change")
    return repo, base_sha, head_sha


def _proof(repo: Path, base_sha: str) -> dict[str, object]:
    return prove_change(
        repo,
        base_ref=base_sha,
        command=[sys.executable, "tests/check.py"],
        repository="example/subject",
        timeout_seconds=20,
    )


def _decision(source: dict[str, object]):  # type: ignore[no-untyped-def]
    policy = load_policy(ROOT / "aos_workflow_gate" / "packs" / "code-change-proof.yml")
    return evaluate(build_bundle(source), policy)


def test_change_proof_passes_when_tests_distinguish_the_change(
    tmp_path: Path,
) -> None:
    repo, base_sha, head_sha = _repository(tmp_path, head_expectation=2)

    source = _proof(repo, base_sha)

    assert source["status"] == SUCCESS
    assert validate_source_v0(source) == source
    identity = source["identity"]
    assert isinstance(identity, dict)
    assert identity["head_sha"] == head_sha
    assert identity["implementation_paths"] == ["app.py"]
    assert len(identity["head_runs"]) == 1
    assert len(identity["challenge_runs"]) == 2
    assert _decision(source).verdict == "PASS"
    assert len(_git(repo, "worktree", "list", "--porcelain").split("worktree ")) == 2


def test_change_proof_warns_when_tests_pass_without_the_change(
    tmp_path: Path,
) -> None:
    repo, base_sha, _head_sha = _repository(tmp_path, head_expectation=1)
    _write(
        repo,
        "tests/check.py",
        "from app import value\nassert value() > 0\n",
    )
    _commit(repo, "make test insensitive")

    source = _proof(repo, base_sha)
    decision = _decision(source)

    assert source["status"] == NOT_DISTINGUISHED
    identity = source["identity"]
    assert isinstance(identity, dict)
    assert len(identity["challenge_runs"]) == 2
    assert decision.verdict == "WARN"
    assert decision.reasons[0].rule == "change_not_distinguished"


def test_change_proof_excludes_root_test_files_by_default(
    tmp_path: Path,
) -> None:
    repo, base_sha, _head_sha = _repository(tmp_path, head_expectation=2)
    _write(repo, "test.py", "assert True\n")
    _commit(repo, "add root test")

    source = _proof(repo, base_sha)

    identity = source["identity"]
    assert isinstance(identity, dict)
    assert identity["implementation_paths"] == ["app.py"]


def test_unstable_challenge_is_inconclusive_not_insensitive(
    tmp_path: Path,
) -> None:
    repo, base_sha, _head_sha = _repository(tmp_path, head_expectation=2)
    counter = tmp_path / "run-count.txt"
    script = (
        "from pathlib import Path; "
        f"p=Path({str(counter)!r}); "
        "n=int(p.read_text())+1 if p.exists() else 1; "
        "p.write_text(str(n)); "
        "raise SystemExit(1 if n == 3 else 0)"
    )

    source = prove_change(
        repo,
        base_ref=base_sha,
        command=[sys.executable, "-c", script],
        repository="example/subject",
        timeout_seconds=20,
    )
    decision = _decision(source)

    assert source["status"] == INCONCLUSIVE
    identity = source["identity"]
    assert isinstance(identity, dict)
    assert [run["state"] for run in identity["challenge_runs"]] == [
        "passed",
        "failed",
    ]
    assert decision.verdict == "WARN"
    assert decision.reasons[0].rule == "verification_inconclusive"


def test_change_proof_blocks_only_after_repeated_head_failure(
    tmp_path: Path,
) -> None:
    repo, base_sha, _head_sha = _repository(tmp_path, head_expectation=3)

    source = _proof(repo, base_sha)
    decision = _decision(source)

    assert source["status"] == CONFIRMED_FAILURE
    identity = source["identity"]
    assert isinstance(identity, dict)
    assert len(identity["head_runs"]) == 2
    assert identity["challenge_runs"] == []
    assert decision.verdict == "BLOCK"
    assert decision.reasons[0].rule == "confirmed_verifier_failure"


def test_change_proof_evidence_contains_digests_not_raw_output(
    tmp_path: Path,
) -> None:
    repo, base_sha, _head_sha = _repository(tmp_path, head_expectation=2)
    secret = "DO-NOT-RECORD-THIS"
    _write(
        repo,
        "tests/check.py",
        f"from app import value\nprint({secret!r})\nassert value() == 2\n",
    )
    _commit(repo, "emit verifier output")

    source = _proof(repo, base_sha)

    encoded = json.dumps(source, sort_keys=True)
    assert secret not in encoded
    assert "stdout_digest" in encoded
    assert source["digest"] == canonical.digest(source["identity"])


def test_change_proof_rejects_subject_mismatch_and_empty_selection(
    tmp_path: Path,
) -> None:
    repo, base_sha, _head_sha = _repository(tmp_path, head_expectation=2)
    with pytest.raises(InputError, match="does not match HEAD"):
        prove_change(
            repo,
            base_ref=base_sha,
            command=[sys.executable, "tests/check.py"],
            expected_sha="0" * 40,
        )
    with pytest.raises(InputError, match="no implementation files selected"):
        prove_change(
            repo,
            base_ref=base_sha,
            command=[sys.executable, "tests/check.py"],
            include=["docs/**"],
        )


def test_change_proof_normalizes_github_origin_identity(
    tmp_path: Path,
) -> None:
    repo, base_sha, _head_sha = _repository(tmp_path, head_expectation=2)
    _git(
        repo,
        "remote",
        "add",
        "origin",
        "git@github.com:example/subject.git",
    )

    source = prove_change(
        repo,
        base_ref=base_sha,
        command=[sys.executable, "tests/check.py"],
        timeout_seconds=20,
    )

    identity = source["identity"]
    assert isinstance(identity, dict)
    assert identity["repository"] == "example/subject"


def test_timeout_is_inconclusive_and_never_blocks(tmp_path: Path) -> None:
    repo, base_sha, _head_sha = _repository(tmp_path, head_expectation=2)

    source = prove_change(
        repo,
        base_ref=base_sha,
        command=[
            sys.executable,
            "-c",
            "import time; time.sleep(1)",
        ],
        repository="example/subject",
        timeout_seconds=0.01,
    )
    decision = _decision(source)

    assert source["status"] == INCONCLUSIVE
    assert decision.verdict == "WARN"
    assert decision.reasons[0].rule == "verification_inconclusive"


def test_cli_writes_replayable_pass_record(tmp_path: Path) -> None:
    repo, base_sha, head_sha = _repository(tmp_path, head_expectation=2)
    out_dir = tmp_path / "evidence"
    record_path = out_dir / "record.json"
    bundle_path = out_dir / "bundle.json"
    policy_path = out_dir / "policy.json"
    source_path = out_dir / "source.json"

    result = cli.main(
        [
            "prove-change",
            "--repo",
            str(repo),
            "--base",
            base_sha,
            "--repository",
            "example/subject",
            "--sha",
            head_sha,
            "--out",
            str(record_path),
            "--bundle-out",
            str(bundle_path),
            "--policy-out",
            str(policy_path),
            "--source-out",
            str(source_path),
            "--",
            sys.executable,
            "tests/check.py",
        ]
    )

    assert result == 0
    record = json.loads(record_path.read_text(encoding="utf-8"))
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    assert record["verdict"] == "PASS"
    assert record["input_bundle_digest"] == canonical.digest(bundle)
    assert (
        cli.main(["verify", "--input", str(record_path), "--bundle", str(bundle_path)])
        == 0
    )
    assert (
        cli.main(
            [
                "summarize",
                "--input",
                str(record_path),
                "--bundle",
                str(bundle_path),
                "--policy",
                str(policy_path),
            ]
        )
        == 0
    )
    diagnosis = diagnose(record)
    assert "failed after AOS removed" in diagnosis["finding"]
    assert "bounded change sensitivity" in diagnosis["scope"]
    assert "not proof of correctness" in diagnosis["scope"]
    assert record["observation"]["change_proof"] == {
        "schema_version": "aos-change-proof/v0",
        "base_sha": base_sha,
        "merge_base_sha": base_sha,
        "head_sha": head_sha,
        "implementation_paths": 1,
        "status": "success",
    }
    assert diagnosis["remediation"]["code"] == "continue_change_proof_validation"
    assert "keep this experiment advisory" in diagnosis["next"]
    assert source_path.is_file()
    assert policy_path.is_file()
