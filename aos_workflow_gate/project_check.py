"""Zero-configuration local project verification without a Git requirement.

The product-facing operation discovers conventional build and test surfaces,
runs them directly (never through a shell), and returns one bounded source-v0
observation. Raw tool output is available to the local caller for diagnosis
but is deliberately excluded from replayable evidence.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from . import canonical
from .errors import InputError
from .source_contract import source_digest

SCHEMA_VERSION = "aos-project-check/v0"
SOURCE_ID = "code.project-check"
SOURCE_KIND = "aos_project_check"
SIGNAL_SOURCE = "local_project_check"

SUCCESS = "success"
FAILED = "failed"
LIMITED = "limited"
INCONCLUSIVE = "inconclusive"
QUALITY_WARNING = "quality_warning"

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
_MANIFEST_NAMES = frozenset(
    {
        "Cargo.lock",
        "Cargo.toml",
        "build.gradle",
        "build.gradle.kts",
        "go.mod",
        "go.sum",
        "package-lock.json",
        "package.json",
        "pnpm-lock.yaml",
        "pom.xml",
        "pyproject.toml",
        "requirements.txt",
        "setup.cfg",
        "setup.py",
        "uv.lock",
        "yarn.lock",
    }
)
_IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "coverage",
        "dist",
        "node_modules",
        "target",
        "vendor",
        "venv",
    }
)
_MAX_SNAPSHOT_FILES = 10_000
_MAX_SNAPSHOT_BYTES = 100 * 1024 * 1024
_MAX_PREVIEW_BYTES = 8 * 1024


@dataclass(frozen=True)
class CheckSpec:
    """One conventional project command selected by a built-in adapter."""

    check_id: str
    label: str
    category: str
    command: tuple[str, ...]


@dataclass(frozen=True)
class CheckRun:
    """Local result plus a bounded preview excluded from source identity."""

    spec: CheckSpec
    state: str
    exit_code: int | None
    elapsed_ms: int
    stdout_digest: str
    stderr_digest: str
    stdout_bytes: int
    stderr_bytes: int
    preview: str

    def as_identity(self) -> dict[str, Any]:
        command = _identity_command(self.spec)
        return {
            "id": self.spec.check_id,
            "label": self.spec.label,
            "category": self.spec.category,
            "command": list(command),
            "command_digest": canonical.digest(list(command)),
            "state": self.state,
            "exit_code": self.exit_code,
            "elapsed_ms": self.elapsed_ms,
            "stdout_digest": self.stdout_digest,
            "stderr_digest": self.stderr_digest,
            "stdout_bytes": self.stdout_bytes,
            "stderr_bytes": self.stderr_bytes,
        }


@dataclass(frozen=True)
class ProjectPlan:
    ecosystems: tuple[str, ...]
    checks: tuple[CheckSpec, ...]
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class ProjectCheckResult:
    source: dict[str, Any]
    runs: tuple[CheckRun, ...]


def check_project(
    project_path: Path,
    *,
    timeout_seconds: float = 300.0,
    custom_command: tuple[str, ...] = (),
) -> ProjectCheckResult:
    """Discover and execute a bounded local verification plan.

    Git metadata is neither read nor required. The function never installs
    dependencies and never invokes a shell. A custom command, when supplied,
    is treated as a behavioral test selected explicitly by the operator.
    """
    root = project_path.resolve()
    if not root.is_dir():
        raise InputError(f"check-project: {project_path} is not a directory")
    timeout = _validate_timeout(timeout_seconds)
    plan = discover_project(root, custom_command=custom_command)
    snapshot_digest, snapshot_files, snapshot_complete = _snapshot(root)
    runs = tuple(_run_check(root, spec, timeout) for spec in plan.checks)
    status = _status(plan, runs, snapshot_complete=snapshot_complete)
    identity: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "project_name": root.name,
        "ecosystems": list(plan.ecosystems),
        "snapshot_digest": snapshot_digest,
        "snapshot_files": snapshot_files,
        "snapshot_complete": snapshot_complete,
        "checks": [run.as_identity() for run in runs],
        "execution_environment": {
            "AOS_PROJECT_CHECK": "1",
            "CI": "true",
            "NO_COLOR": "1",
            "PYTHONPYCACHEPREFIX": "<temporary>",
        },
        "limitations": list(plan.limitations),
        "status": status,
    }
    source = {
        "id": SOURCE_ID,
        "kind": SOURCE_KIND,
        "status": status,
        "digest": source_digest(identity),
        "summary": _summary(plan, runs, status, snapshot_complete),
        "signal_source": SIGNAL_SOURCE,
        "observed_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "contract": "source-v0",
        "identity": identity,
    }
    return ProjectCheckResult(source=source, runs=runs)


def discover_project(
    root: Path, *, custom_command: tuple[str, ...] = ()
) -> ProjectPlan:
    """Build a deterministic plan from conventional root-level metadata."""
    ecosystems: list[str] = []
    checks: list[CheckSpec] = []
    limitations: list[str] = []

    if _looks_like_python(root):
        ecosystems.append("Python")
        checks.append(
            CheckSpec(
                "python.compile",
                "Python syntax",
                "build",
                (
                    sys.executable,
                    "-m",
                    "compileall",
                    "-q",
                    "-x",
                    r"(^|[\\/])(\.git|\.venv|venv|node_modules|build|dist)([\\/]|$)",
                    ".",
                ),
            )
        )
        if _python_has_tests(root):
            if importlib.util.find_spec("pytest") is None:
                limitations.append(
                    "Python tests were found, but pytest is not installed "
                    "in the current environment."
                )
            else:
                checks.append(
                    CheckSpec(
                        "python.tests",
                        "Python tests",
                        "test",
                        (sys.executable, "-m", "pytest", "-q"),
                    )
                )

    package_path = root / "package.json"
    if package_path.is_file():
        ecosystems.append("Node.js")
        _add_node_checks(root, package_path, checks, limitations)

    if (root / "go.mod").is_file():
        ecosystems.append("Go")
        _add_tool_check(
            checks,
            limitations,
            executable="go",
            spec=CheckSpec("go.tests", "Go tests", "test", ("go", "test", "./...")),
        )

    if (root / "Cargo.toml").is_file():
        ecosystems.append("Rust")
        _add_tool_check(
            checks,
            limitations,
            executable="cargo",
            spec=CheckSpec(
                "rust.tests", "Rust tests", "test", ("cargo", "test", "--quiet")
            ),
        )

    if (root / "pom.xml").is_file():
        ecosystems.append("Java/Maven")
        executable = "mvn.cmd" if os.name == "nt" else "mvn"
        _add_tool_check(
            checks,
            limitations,
            executable=executable,
            spec=CheckSpec(
                "maven.tests", "Maven tests", "test", (executable, "test", "-q")
            ),
        )
    elif (root / "gradlew").is_file() or (root / "gradlew.bat").is_file():
        ecosystems.append("Java/Gradle")
        executable = "gradlew.bat" if os.name == "nt" else "./gradlew"
        checks.append(
            CheckSpec(
                "gradle.tests", "Gradle tests", "test", (executable, "test", "--quiet")
            )
        )

    if custom_command:
        checks.append(
            CheckSpec(
                "custom.verifier",
                "Custom verification",
                "test",
                _validate_command(custom_command),
            )
        )

    if not ecosystems:
        limitations.append(
            "No supported root project was detected (Python, Node.js, Go, "
            "Rust, Maven, or Gradle)."
        )
    if not any(spec.category == "test" for spec in checks):
        limitations.append("No runnable behavioral test was discovered.")

    return ProjectPlan(
        ecosystems=tuple(dict.fromkeys(ecosystems)),
        checks=tuple(_deduplicate_checks(checks)),
        limitations=tuple(dict.fromkeys(limitations)),
    )


def build_bundle(source: dict[str, Any]) -> dict[str, Any]:
    """Build a local, replayable bundle without pretending a Git SHA exists."""
    identity = source.get("identity")
    if not isinstance(identity, dict):
        raise InputError("check-project: source identity is missing")
    project_name = identity.get("project_name")
    if not isinstance(project_name, str) or not project_name:
        raise InputError("check-project: project identity is malformed")
    return {
        "schema_version": "draft-0",
        "subject": {
            "repository": f"local/{project_name}",
            "ref": None,
            "sha": None,
            "pull_request": None,
        },
        "sources": [source],
        "collection": {
            "status": "complete",
            "observed_at": source.get("observed_at"),
            "project_check": {
                "schema_version": identity.get("schema_version"),
                "snapshot_digest": identity.get("snapshot_digest"),
                "snapshot_files": identity.get("snapshot_files"),
                "snapshot_complete": identity.get("snapshot_complete"),
                "ecosystems": identity.get("ecosystems"),
                "checks": len(identity.get("checks") or []),
                "status": source.get("status"),
            },
        },
    }


def _add_node_checks(
    root: Path,
    package_path: Path,
    checks: list[CheckSpec],
    limitations: list[str],
) -> None:
    try:
        package = json.loads(package_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        limitations.append("package.json could not be read as valid JSON.")
        return
    scripts = package.get("scripts") if isinstance(package, dict) else None
    if not isinstance(scripts, dict):
        limitations.append("package.json defines no runnable scripts.")
        return
    manager = _node_manager(root)
    executable = shutil.which(manager)
    if executable is None:
        limitations.append(
            f"{manager} is required by the project but is not available."
        )
        return
    for name, label, category in (
        ("build", "Node build", "build"),
        ("typecheck", "Node type check", "build"),
        ("test", "Node tests", "test"),
        ("lint", "Node lint", "quality"),
    ):
        value = scripts.get(name)
        if not isinstance(value, str) or not value.strip():
            continue
        if name == "test" and "no test specified" in value.lower():
            continue
        command = (executable, name) if manager == "yarn" else (executable, "run", name)
        checks.append(CheckSpec(f"node.{name}", label, category, command))


def _node_manager(root: Path) -> str:
    if (root / "pnpm-lock.yaml").is_file():
        return "pnpm"
    if (root / "yarn.lock").is_file():
        return "yarn"
    if (root / "bun.lock").is_file() or (root / "bun.lockb").is_file():
        return "bun"
    return "npm"


def _add_tool_check(
    checks: list[CheckSpec],
    limitations: list[str],
    *,
    executable: str,
    spec: CheckSpec,
) -> None:
    resolved = shutil.which(executable)
    if resolved is None:
        limitations.append(
            f"{executable} is required by the project but is not available."
        )
        return
    checks.append(
        CheckSpec(
            spec.check_id, spec.label, spec.category, (resolved, *spec.command[1:])
        )
    )


def _deduplicate_checks(checks: list[CheckSpec]) -> list[CheckSpec]:
    seen: set[str] = set()
    result = []
    for spec in checks:
        if spec.check_id in seen:
            continue
        seen.add(spec.check_id)
        result.append(spec)
    return result


def _looks_like_python(root: Path) -> bool:
    if any(
        (root / name).is_file() for name in ("pyproject.toml", "setup.py", "setup.cfg")
    ):
        return True
    if any(path.is_file() for path in root.glob("*.py")):
        return True
    source = root / "src"
    return source.is_dir() and any(path.is_file() for path in source.rglob("*.py"))


def _python_has_tests(root: Path) -> bool:
    if any((root / name).is_file() for name in ("pytest.ini", "tox.ini")):
        return True
    for name in ("test", "tests"):
        directory = root / name
        if directory.is_dir() and any(
            path.is_file() for path in directory.rglob("*.py")
        ):
            return True
    if any(root.glob("test_*.py")) or any(root.glob("*_test.py")):
        return True
    pyproject = root / "pyproject.toml"
    if not pyproject.is_file():
        return False
    try:
        return "[tool.pytest" in pyproject.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False


def _identity_command(spec: CheckSpec) -> tuple[str, ...]:
    """Return a portable command identity without leaking a host tool path."""
    if not spec.command or spec.check_id == "custom.verifier":
        return spec.command
    executable_by_prefix = {
        "go.": "go",
        "maven.": "mvn",
        "python.": "python",
        "rust.": "cargo",
    }
    for prefix, executable in executable_by_prefix.items():
        if spec.check_id.startswith(prefix):
            return (executable, *spec.command[1:])
    if spec.check_id.startswith("node."):
        executable = Path(spec.command[0]).name.lower()
        for suffix in (".cmd", ".exe", ".bat"):
            if executable.endswith(suffix):
                executable = executable[: -len(suffix)]
                break
        return (executable, *spec.command[1:])
    return spec.command


def _validate_timeout(value: float) -> float:
    if not math.isfinite(value) or value <= 0 or value > 3600:
        raise InputError(
            "check-project: --timeout-seconds must be greater than 0 and at most 3600"
        )
    return value


def _validate_command(command: tuple[str, ...]) -> tuple[str, ...]:
    argv = command[1:] if command and command[0] == "--" else command
    if not argv:
        raise InputError("check-project: custom verifier command is empty")
    if any(not arg or "\x00" in arg for arg in argv):
        raise InputError(
            "check-project: command arguments must be non-empty and contain no NUL"
        )
    return tuple(argv)


def _snapshot(root: Path) -> tuple[str, int, bool]:
    digest = hashlib.sha256()
    count = 0
    size = 0
    complete = True
    for directory, names, files in os.walk(root, followlinks=False):
        names[:] = sorted(name for name in names if name not in _IGNORED_DIRECTORIES)
        for name in sorted(files):
            path = Path(directory, name)
            if path.is_symlink() or not _snapshot_candidate(path):
                continue
            try:
                stat = path.stat()
            except OSError:
                complete = False
                continue
            if (
                count >= _MAX_SNAPSHOT_FILES
                or size + stat.st_size > _MAX_SNAPSHOT_BYTES
            ):
                complete = False
                continue
            relative = PurePosixPath(path.relative_to(root)).as_posix()
            file_digest = hashlib.sha256()
            try:
                with path.open("rb") as stream:
                    while chunk := stream.read(64 * 1024):
                        file_digest.update(chunk)
            except OSError:
                complete = False
                continue
            encoded_path = relative.encode("utf-8")
            digest.update(len(encoded_path).to_bytes(4, "big"))
            digest.update(encoded_path)
            digest.update(file_digest.digest())
            count += 1
            size += stat.st_size
    return "sha256:" + digest.hexdigest(), count, complete


def _snapshot_candidate(path: Path) -> bool:
    return path.name in _MANIFEST_NAMES or path.suffix.lower() in _CODE_SUFFIXES


def _run_check(root: Path, spec: CheckSpec, timeout: float) -> CheckRun:
    started = time.monotonic()
    env = os.environ.copy()
    env["CI"] = "true"
    env["NO_COLOR"] = "1"
    env["AOS_PROJECT_CHECK"] = "1"
    with (
        tempfile.TemporaryDirectory(prefix="aos-pycache-") as pycache,
        tempfile.TemporaryFile() as stdout,
        tempfile.TemporaryFile() as stderr,
    ):
        env["PYTHONPYCACHEPREFIX"] = pycache
        try:
            completed = subprocess.run(
                list(spec.command),
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                timeout=timeout,
                env=env,
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
        stdout_digest, stdout_bytes = _stream_digest(stdout)
        stderr_digest, stderr_bytes = _stream_digest(stderr)
        preview = _preview(stdout, stderr)
    return CheckRun(
        spec=spec,
        state=state,
        exit_code=exit_code,
        elapsed_ms=elapsed_ms,
        stdout_digest=stdout_digest,
        stderr_digest=stderr_digest,
        stdout_bytes=stdout_bytes,
        stderr_bytes=stderr_bytes,
        preview=preview,
    )


def _stream_digest(stream: Any) -> tuple[str, int]:
    stream.flush()
    stream.seek(0)
    digest = hashlib.sha256()
    size = 0
    while chunk := stream.read(64 * 1024):
        digest.update(chunk)
        size += len(chunk)
    return "sha256:" + digest.hexdigest(), size


def _preview(stdout: Any, stderr: Any) -> str:
    values = []
    for stream in (stderr, stdout):
        stream.flush()
        stream.seek(0, os.SEEK_END)
        length = stream.tell()
        stream.seek(max(0, length - _MAX_PREVIEW_BYTES))
        value = stream.read(_MAX_PREVIEW_BYTES)
        if value:
            values.append(value.decode("utf-8", errors="replace").strip())
    return "\n".join(value for value in values if value)


def _status(
    plan: ProjectPlan,
    runs: tuple[CheckRun, ...],
    *,
    snapshot_complete: bool,
) -> str:
    if any(run.state == "failed" and run.spec.category != "quality" for run in runs):
        return FAILED
    if any(run.state in {"timeout", "launch_error"} for run in runs):
        return INCONCLUSIVE
    if (
        not runs
        or plan.limitations
        or not snapshot_complete
        or not any(run.spec.category == "test" for run in runs)
    ):
        return LIMITED
    if any(run.state == "failed" for run in runs):
        return QUALITY_WARNING
    return SUCCESS


def _summary(
    plan: ProjectPlan,
    runs: tuple[CheckRun, ...],
    status: str,
    snapshot_complete: bool,
) -> str:
    if status == FAILED:
        failed = next(
            run
            for run in runs
            if run.state == "failed" and run.spec.category != "quality"
        )
        return (
            f"{failed.spec.label} failed with exit code {failed.exit_code}; "
            "the project is not ready to ship."
        )
    if status == INCONCLUSIVE:
        incomplete = next(
            run for run in runs if run.state in {"timeout", "launch_error"}
        )
        return (
            f"{incomplete.spec.label} could not complete ({incomplete.state}); "
            "project verification is inconclusive."
        )
    if status == QUALITY_WARNING:
        warning = next(run for run in runs if run.state == "failed")
        return (
            f"{warning.spec.label} reported issues with exit code "
            f"{warning.exit_code}; build and test results remain separate."
        )
    if status == LIMITED:
        if not snapshot_complete:
            return "The project snapshot exceeded the bounded local verification limit."
        if plan.limitations:
            return plan.limitations[0]
        return "No runnable behavioral test was discovered."
    return f"All {len(runs)} discovered project checks passed."
