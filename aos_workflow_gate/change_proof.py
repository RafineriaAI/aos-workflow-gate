"""Executable change-sensitivity proof for one exact Git commit.

The verifier runs an operator-supplied command in disposable Git worktrees:
first at ``HEAD``, then with the changed implementation files restored from
the merge base while PR tests remain at ``HEAD``.  The result answers one
bounded question: do the supplied checks distinguish this implementation
change from its base?

No shell is involved, no command is read from repository content, and no raw
command output enters evidence.  The generated ``source-v0`` source contains
only exact subject identities, command/path digests, exit states, durations,
and output digests.
"""

from __future__ import annotations

import fnmatch
import hashlib
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from . import canonical
from .errors import InputError
from .source_contract import source_digest

SCHEMA_VERSION = "aos-change-proof/v0"
SOURCE_ID = "code.change-proof"
SOURCE_KIND = "aos_change_proof"
SIGNAL_SOURCE = "local_change_proof"

SUCCESS = "success"
CONFIRMED_FAILURE = "confirmed_failure"
NOT_DISTINGUISHED = "not_distinguished"
INCONCLUSIVE = "inconclusive"

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_CODE_SUFFIXES = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".go",
        ".h",
        ".hpp",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".kts",
        ".php",
        ".py",
        ".rb",
        ".rs",
        ".swift",
        ".ts",
        ".tsx",
    }
)
_TEST_SEGMENTS = frozenset({"test", "tests", "spec", "specs", "__tests__"})
_IGNORED_SEGMENTS = frozenset(
    {".git", "benchmarks", "docs", "examples", "fixtures", "vendor"}
)
_MAX_PATHS = 200
_MAX_COMMAND_ARGS = 128
_MAX_COMMAND_CHARS = 16_384


@dataclass(frozen=True)
class CommandResult:
    """Bounded, non-secret projection of one command execution."""

    state: str
    exit_code: int | None
    elapsed_ms: int
    stdout_digest: str
    stderr_digest: str
    stdout_bytes: int
    stderr_bytes: int

    def as_identity(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "exit_code": self.exit_code,
            "elapsed_ms": self.elapsed_ms,
            "stdout_digest": self.stdout_digest,
            "stderr_digest": self.stderr_digest,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
        }


def prove_change(
    repository_path: Path,
    *,
    base_ref: str,
    command: Sequence[str],
    repository: str | None = None,
    expected_sha: str | None = None,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    timeout_seconds: float = 300.0,
) -> dict[str, Any]:
    """Return a strict ``source-v0`` change-sensitivity observation.

    ``confirmed_failure`` requires the operator command to fail twice on two
    clean worktrees at the exact head SHA.  A positive sensitivity result
    likewise requires two clean challenge runs to fail after implementation
    changes are removed.  Any unstable or operational state is
    ``inconclusive``; it is never promoted to a confirmed result.
    """
    repo = _repository_root(repository_path)
    argv = _validate_command(command)
    timeout = _validate_timeout(timeout_seconds)
    head_sha = _git_text(repo, "rev-parse", "HEAD")
    base_sha = _git_text(repo, "rev-parse", f"{base_ref}^{{commit}}")
    merge_base_sha = _git_text(repo, "merge-base", base_sha, head_sha)
    for name, value in (
        ("head SHA", head_sha),
        ("base SHA", base_sha),
        ("merge-base SHA", merge_base_sha),
    ):
        if not _SHA_RE.fullmatch(value):
            raise InputError(f"prove-change: {name} is not a full Git SHA")
    if expected_sha is not None and expected_sha != head_sha:
        raise InputError(
            "prove-change: --sha does not match HEAD: "
            f"expected {expected_sha}, observed {head_sha}"
        )

    changed_paths = _changed_paths(repo, merge_base_sha, head_sha)
    implementation_paths = _implementation_paths(
        changed_paths, include=include, exclude=exclude
    )
    if not implementation_paths:
        raise InputError(
            "prove-change: no implementation files selected; use --source "
            "GLOB to select decision-relevant code paths explicitly"
        )
    if len(implementation_paths) > _MAX_PATHS:
        raise InputError(
            f"prove-change: selected {len(implementation_paths)} files; "
            f"the bounded v0 limit is {_MAX_PATHS}. Narrow --source patterns."
        )

    patch = _git_bytes(
        repo,
        "diff",
        "--binary",
        "--no-renames",
        merge_base_sha,
        head_sha,
        "--",
        *implementation_paths,
    )
    if not patch:
        raise InputError(
            "prove-change: selected implementation paths produced no patch"
        )

    head_runs: list[CommandResult] = []
    challenge_runs: list[CommandResult] = []
    head_runs.append(_run_in_head(repo, head_sha, argv, timeout))
    first_head = head_runs[0]

    if first_head.state == "failed":
        head_runs.append(_run_in_head(repo, head_sha, argv, timeout))
        status = CONFIRMED_FAILURE if _stable_failure(head_runs) else INCONCLUSIVE
    elif first_head.state != "passed":
        status = INCONCLUSIVE
    else:
        challenge_runs.append(_run_in_challenge(repo, head_sha, patch, argv, timeout))
        first_challenge = challenge_runs[0]
        if first_challenge.state == "passed":
            challenge_runs.append(
                _run_in_challenge(repo, head_sha, patch, argv, timeout)
            )
            status = NOT_DISTINGUISHED if _stable_pass(challenge_runs) else INCONCLUSIVE
        elif first_challenge.state == "failed":
            challenge_runs.append(
                _run_in_challenge(repo, head_sha, patch, argv, timeout)
            )
            status = SUCCESS if _stable_failure(challenge_runs) else INCONCLUSIVE
        else:
            status = INCONCLUSIVE

    repository_id = repository or _repository_identity(repo)
    identity: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "repository": repository_id,
        "base_sha": base_sha,
        "merge_base_sha": merge_base_sha,
        "head_sha": head_sha,
        "command": list(argv),
        "command_digest": canonical.digest(list(argv)),
        "implementation_paths": implementation_paths,
        "implementation_paths_digest": canonical.digest(implementation_paths),
        "implementation_patch_digest": _bytes_digest(patch),
        "head_runs": [result.as_identity() for result in head_runs],
        "challenge_runs": [result.as_identity() for result in challenge_runs],
        "status": status,
    }
    return {
        "id": SOURCE_ID,
        "kind": SOURCE_KIND,
        "status": status,
        "digest": source_digest(identity),
        "summary": _summary(status, len(implementation_paths), head_runs),
        "signal_source": SIGNAL_SOURCE,
        "observed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "contract": "source-v0",
        "identity": identity,
    }


def build_bundle(source: dict[str, Any]) -> dict[str, Any]:
    """Build a replayable one-source bundle from a change-proof source."""
    identity = source.get("identity")
    if not isinstance(identity, dict):
        raise InputError("prove-change: source identity is missing")
    repository = identity.get("repository")
    head_sha = identity.get("head_sha")
    if not isinstance(repository, str) or not isinstance(head_sha, str):
        raise InputError("prove-change: source subject is malformed")
    return {
        "schema_version": "draft-0",
        "subject": {
            "repository": repository,
            "ref": "HEAD",
            "sha": head_sha,
            "pull_request": None,
        },
        "sources": [source],
        "collection": {
            "status": "complete",
            "observed_at": source.get("observed_at"),
            "observation_scope": {
                "repository": repository,
                "head_sha": head_sha,
            },
            "change_proof": {
                "schema_version": identity.get("schema_version"),
                "base_sha": identity.get("base_sha"),
                "merge_base_sha": identity.get("merge_base_sha"),
                "head_sha": head_sha,
                "implementation_paths": len(identity.get("implementation_paths") or []),
                "status": source.get("status"),
            },
        },
    }


def _validate_command(command: Sequence[str]) -> tuple[str, ...]:
    argv = tuple(command)
    if argv and argv[0] == "--":
        argv = argv[1:]
    if not argv:
        raise InputError(
            "prove-change: provide an explicit verifier command after '--'"
        )
    if len(argv) > _MAX_COMMAND_ARGS:
        raise InputError(f"prove-change: command exceeds {_MAX_COMMAND_ARGS} arguments")
    if any(not isinstance(arg, str) or not arg or "\x00" in arg for arg in argv):
        raise InputError(
            "prove-change: command arguments must be non-empty strings without NUL"
        )
    if sum(len(arg) for arg in argv) > _MAX_COMMAND_CHARS:
        raise InputError(
            f"prove-change: command exceeds {_MAX_COMMAND_CHARS} characters"
        )
    return argv


def _validate_timeout(value: float) -> float:
    if not math.isfinite(value) or value <= 0 or value > 3600:
        raise InputError(
            "prove-change: --timeout-seconds must be greater than 0 and at most 3600"
        )
    return value


def _repository_root(path: Path) -> Path:
    try:
        root = _git_text(path.resolve(), "rev-parse", "--show-toplevel")
    except InputError as exc:
        raise InputError(f"prove-change: {path} is not inside a Git worktree") from exc
    return Path(root).resolve()


def _repository_identity(repo: Path) -> str:
    result = subprocess.run(
        ["git", "config", "--get", "remote.origin.url"],
        cwd=repo,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
        encoding="utf-8",
    )
    remote = result.stdout.strip() if result.returncode == 0 else ""
    match = re.search(
        r"(?:github\.com[/:])(?P<slug>[^/\s:]+/[^/\s]+?)(?:\.git)?$",
        remote,
    )
    if match:
        return match.group("slug")
    return f"local/{repo.name}"


def _changed_paths(repo: Path, base_sha: str, head_sha: str) -> list[str]:
    payload = _git_bytes(
        repo,
        "diff",
        "--name-only",
        "--no-renames",
        "-z",
        base_sha,
        head_sha,
        "--",
    )
    paths = []
    for raw in payload.split(b"\x00"):
        if not raw:
            continue
        try:
            path = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise InputError("prove-change: changed path is not valid UTF-8") from exc
        normalized = PurePosixPath(path).as_posix()
        if normalized.startswith("../") or normalized.startswith("/"):
            raise InputError("prove-change: Git returned an unsafe path")
        paths.append(normalized)
    return sorted(set(paths))


def _implementation_paths(
    changed_paths: Sequence[str],
    *,
    include: Sequence[str],
    exclude: Sequence[str],
) -> list[str]:
    selected = []
    for path in changed_paths:
        if include:
            if not any(fnmatch.fnmatchcase(path, pattern) for pattern in include):
                continue
        elif not _default_implementation_path(path):
            continue
        if any(fnmatch.fnmatchcase(path, pattern) for pattern in exclude):
            continue
        selected.append(path)
    return sorted(selected)


def _default_implementation_path(path: str) -> bool:
    pure = PurePosixPath(path)
    lowered_parts = tuple(part.lower() for part in pure.parts)
    if any(part in _TEST_SEGMENTS for part in lowered_parts):
        return False
    if any(part in _IGNORED_SEGMENTS for part in lowered_parts):
        return False
    name = pure.name.lower()
    if pure.stem.lower() in {"test", "tests", "spec", "specs"}:
        return False
    if (
        name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
    ):
        return False
    return pure.suffix.lower() in _CODE_SUFFIXES


def _run_in_head(
    repo: Path, head_sha: str, command: Sequence[str], timeout: float
) -> CommandResult:
    with _temporary_worktree(repo, head_sha) as worktree:
        return _run_command(command, worktree, timeout)


def _run_in_challenge(
    repo: Path,
    head_sha: str,
    reverse_patch: bytes,
    command: Sequence[str],
    timeout: float,
) -> CommandResult:
    with _temporary_worktree(repo, head_sha) as worktree:
        applied = subprocess.run(
            [
                "git",
                "apply",
                "--reverse",
                "--index",
                "--binary",
                "--whitespace=nowarn",
                "-",
            ],
            cwd=worktree,
            input=reverse_patch,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if applied.returncode != 0:
            return _empty_result("patch_error")
        return _run_command(command, worktree, timeout)


@contextmanager
def _temporary_worktree(repo: Path, sha: str) -> Iterator[Path]:
    root = Path(tempfile.mkdtemp(prefix="aos-change-proof-"))
    added = False
    try:
        _git_text(repo, "worktree", "add", "--detach", "--force", str(root), sha)
        added = True
        yield root
    finally:
        if added:
            subprocess.run(
                ["git", "worktree", "remove", "--force", str(root)],
                cwd=repo,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        if root.exists():
            shutil.rmtree(root, ignore_errors=True)
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=repo,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )


def _run_command(
    command: Sequence[str], worktree: Path, timeout: float
) -> CommandResult:
    env = os.environ.copy()
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(worktree)
        if not existing_pythonpath
        else str(worktree) + os.pathsep + existing_pythonpath
    )
    env["AOS_PROOF_WORKTREE"] = str(worktree)
    started = time.monotonic()
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            completed = subprocess.run(
                list(command),
                cwd=worktree,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                check=False,
                shell=False,
            )
            state = "passed" if completed.returncode == 0 else "failed"
            exit_code: int | None = completed.returncode
        except subprocess.TimeoutExpired:
            state = "timeout"
            exit_code = None
        except (FileNotFoundError, PermissionError, OSError):
            state = "launch_error"
            exit_code = None
        elapsed_ms = max(0, int((time.monotonic() - started) * 1000))
        stdout_digest, stdout_bytes = _file_digest(stdout)
        stderr_digest, stderr_bytes = _file_digest(stderr)
    return CommandResult(
        state=state,
        exit_code=exit_code,
        elapsed_ms=elapsed_ms,
        stdout_digest=stdout_digest,
        stderr_digest=stderr_digest,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
    )


def _stable_failure(results: Sequence[CommandResult]) -> bool:
    return (
        len(results) == 2
        and all(result.state == "failed" for result in results)
        and results[0].exit_code == results[1].exit_code
    )


def _stable_pass(results: Sequence[CommandResult]) -> bool:
    return len(results) == 2 and all(
        result.state == "passed" and result.exit_code == 0 for result in results
    )


def _empty_result(state: str) -> CommandResult:
    empty = _bytes_digest(b"")
    return CommandResult(state, None, 0, empty, empty, 0, 0)


def _file_digest(stream: Any) -> tuple[str, int]:
    stream.flush()
    stream.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(64 * 1024):
        digest.update(chunk)
        size += len(chunk)
    return "sha256:" + digest.hexdigest(), size


def _bytes_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _git_text(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        detail = " ".join(result.stderr.split())
        if len(detail) > 300:
            detail = detail[:297].rstrip() + "..."
        raise InputError(
            f"prove-change: git {' '.join(args[:2])} failed"
            + (f": {detail}" if detail else "")
        )
    return result.stdout.strip()


def _git_bytes(repo: Path, *args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise InputError(f"prove-change: git {' '.join(args[:2])} failed")
    return result.stdout


def _summary(status: str, path_count: int, head_runs: Sequence[CommandResult]) -> str:
    if status == SUCCESS:
        return (
            "Change proof passed: the verifier succeeded at HEAD and failed "
            f"twice after reverting {path_count} implementation file(s)."
        )
    if status == NOT_DISTINGUISHED:
        return (
            "Change proof gap: the verifier also passed after reverting "
            f"{path_count} implementation file(s)."
        )
    if status == CONFIRMED_FAILURE:
        code = head_runs[0].exit_code if head_runs else None
        return (
            "Change proof failed: the verifier failed twice at the exact "
            f"HEAD with exit code {code}."
        )
    return (
        "Change proof was inconclusive: execution, patch application, or "
        "repeatability did not produce a stable result."
    )
