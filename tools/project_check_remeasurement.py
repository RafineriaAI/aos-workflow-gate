"""Re-measure missing-test warnings on the frozen exact-SHA public corpus.

The tool reconstructs only project metadata and test-path structure. It never
checks out dependencies or executes repository code.
"""

from __future__ import annotations

import argparse
import base64
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aos_workflow_gate.project_check import ProjectPlan, discover_project  # noqa: E402
from tools.mass_value_study import (  # noqa: E402
    _canonical_digest,
    _gh_json,
    _load,
    _rate,
    _write,
)

BASE = ROOT / "benchmarks" / "mass-market"
DEFAULT_MANIFEST = BASE / "project-check-remeasurement-manifest.json"
DEFAULT_GAP_AUDIT = BASE / "gap-audit.json"
DEFAULT_ADJUDICATION = BASE / "gap-audit-adjudication.json"
DEFAULT_OUT = BASE / "project-check-remeasurement.json"
DEFAULT_REPORT = BASE / "PROJECT_CHECK_REMEASUREMENT.md"

_PROJECT_MARKERS = frozenset(
    {
        "Cargo.toml",
        "go.mod",
        "gradlew",
        "gradlew.bat",
        "package.json",
        "pom.xml",
        "pyproject.toml",
        "setup.cfg",
        "setup.py",
    }
)
_LOCAL_METADATA = _PROJECT_MARKERS.union(
    {
        "bun.lock",
        "bun.lockb",
        "pnpm-lock.yaml",
        "pytest.ini",
        "tox.ini",
        "yarn.lock",
    }
)
_CONTENT_METADATA = frozenset({"package.json", "pyproject.toml"})
_MAX_CONTENT_BYTES = 2 * 1024 * 1024

BlobLoader = Callable[[dict[str, Any]], bytes]


def _safe_path(value: str) -> PurePosixPath | None:
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        return None
    return path


def _candidate_roots(entries: list[dict[str, Any]]) -> tuple[str, ...]:
    roots = {"."}
    for entry in entries:
        value = entry.get("path")
        if entry.get("type") != "blob" or not isinstance(value, str):
            continue
        path = _safe_path(value)
        if path is None or path.name not in _PROJECT_MARKERS:
            continue
        parent = path.parent.as_posix()
        if parent == "." or len(path.parent.parts) <= 4:
            roots.add(parent)
    return tuple(sorted(roots))


def _python_evidence_path(path: PurePosixPath, root: str) -> bool:
    base = PurePosixPath() if root == "." else PurePosixPath(root)
    try:
        relative = path.relative_to(base)
    except ValueError:
        return False
    if not relative.parts:
        return False
    if len(relative.parts) == 1:
        return relative.suffix.lower() == ".py" or relative.name in {
            "pytest.ini",
            "tox.ini",
        }
    return relative.suffix.lower() == ".py" and relative.parts[0].lower() in {
        "src",
        "test",
        "tests",
    }


def _selected_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    roots = _candidate_roots(entries)
    selected: dict[str, dict[str, Any]] = {}
    for entry in entries:
        value = entry.get("path")
        if entry.get("type") != "blob" or not isinstance(value, str):
            continue
        path = _safe_path(value)
        if path is None:
            continue
        if path.name in _LOCAL_METADATA or any(
            _python_evidence_path(path, root) for root in roots
        ):
            selected[value] = entry
    return [selected[path] for path in sorted(selected)]


def _materialize(
    root: Path,
    entries: list[dict[str, Any]],
    load_blob: BlobLoader,
) -> tuple[int, bool]:
    fetched = 0
    complete = True
    for entry in _selected_entries(entries):
        value = entry.get("path")
        if not isinstance(value, str):
            continue
        path = _safe_path(value)
        if path is None:
            complete = False
            continue
        target = root.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        content = b""
        if path.name in _CONTENT_METADATA:
            try:
                content = load_blob(entry)
            except (OSError, RuntimeError, ValueError):
                complete = False
                content = b""
            fetched += 1
        target.write_bytes(content)
    return fetched, complete


def _plan(root: Path) -> ProjectPlan:
    with (
        mock.patch(
            "aos_workflow_gate.project_check.shutil.which",
            side_effect=lambda executable: executable,
        ),
        mock.patch(
            "aos_workflow_gate.project_check.importlib.util.find_spec",
            return_value=object(),
        ),
    ):
        return discover_project(root)


def observe_tree(
    repository: dict[str, Any],
    response: dict[str, Any],
    *,
    load_blob: BlobLoader,
    adjudication: str | None = None,
) -> dict[str, Any]:
    raw_tree = response.get("tree")
    entries = (
        [entry for entry in raw_tree if isinstance(entry, dict)]
        if isinstance(raw_tree, list)
        else []
    )
    if response.get("truncated") is True:
        return {
            "adjudication": adjudication,
            "classification": "inconclusive_truncated_tree",
            "complete": False,
            "head_sha": repository["head_sha"],
            "repository": repository["repository"],
        }
    with tempfile.TemporaryDirectory(prefix="aos-remeasurement-") as directory:
        fetched, materialized = _materialize(Path(directory), entries, load_blob)
        plan = _plan(Path(directory))
    tests = [check for check in plan.checks if check.category == "test"]
    nested_tests = [check for check in tests if check.working_directory != "."]
    if nested_tests:
        classification = "resolved_by_nested_command"
    elif tests:
        classification = "root_command_detected"
    else:
        classification = "no_supported_runnable_command"
    return {
        "adjudication": adjudication,
        "classification": classification,
        "complete": materialized,
        "declared_test_checks": [
            {
                "id": check.check_id,
                "working_directory": check.working_directory,
            }
            for check in tests
        ],
        "ecosystems": list(plan.ecosystems),
        "head_sha": repository["head_sha"],
        "limitations": list(plan.limitations),
        "metadata_blobs_fetched": fetched,
        "nested_discovery_complete": plan.nested_discovery_complete,
        "project_roots": list(plan.project_roots),
        "repository": repository["repository"],
    }


def _github_blob_loader(repository: str) -> BlobLoader:
    cache: dict[str, bytes] = {}

    def load(entry: dict[str, Any]) -> bytes:
        sha = entry.get("sha")
        if not isinstance(sha, str) or not sha:
            raise ValueError("metadata entry has no blob sha")
        if sha in cache:
            return cache[sha]
        response = _gh_json(["-X", "GET", f"repos/{repository}/git/blobs/{sha}"])
        content = response.get("content")
        encoding = response.get("encoding")
        if not isinstance(content, str) or encoding != "base64":
            raise ValueError("metadata blob is not base64")
        decoded = base64.b64decode(content, validate=False)
        if len(decoded) > _MAX_CONTENT_BYTES:
            raise ValueError("metadata blob exceeds bounded size")
        cache[sha] = decoded
        return decoded

    return load


def _result(
    manifest: dict[str, Any],
    gap_audit: dict[str, Any],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    counts = Counter(str(row["classification"]) for row in observations)
    complete = [row for row in observations if row.get("complete") is True]
    definite = [
        row for row in complete if row.get("adjudication") == "definite_test_surface"
    ]
    definite_detected = [row for row in definite if row.get("declared_test_checks")]
    nested_resolved = [
        row
        for row in complete
        if row.get("classification") == "resolved_by_nested_command"
    ]
    bounded_complete = [
        row for row in complete if row.get("nested_discovery_complete") is True
    ]
    complete_nested_resolved = [
        row for row in nested_resolved if row.get("nested_discovery_complete") is True
    ]
    definite_complete_detected = [
        row for row in definite_detected if row.get("nested_discovery_complete") is True
    ]
    metrics = {
        "repositories": len(observations),
        "complete_observations": len(complete),
        "complete_observation_rate": _rate(len(complete), len(observations)),
        "nested_command_resolutions": counts["resolved_by_nested_command"],
        "nested_command_resolution_rate": _rate(len(nested_resolved), len(complete)),
        "complete_nested_command_resolutions": len(complete_nested_resolved),
        "complete_nested_command_resolution_rate": _rate(
            len(complete_nested_resolved), len(complete)
        ),
        "root_commands_detected": counts["root_command_detected"],
        "remaining_no_supported_command": counts["no_supported_runnable_command"],
        "bounded_discovery_complete": len(bounded_complete),
        "bounded_discovery_complete_rate": _rate(len(bounded_complete), len(complete)),
        "bounded_discovery_incomplete": len(complete) - len(bounded_complete),
        "definite_test_surfaces": len(definite),
        "definite_surfaces_with_supported_command": len(definite_detected),
        "definite_command_detection_rate": _rate(len(definite_detected), len(definite)),
        "definite_surfaces_with_complete_supported_command": len(
            definite_complete_detected
        ),
    }
    if len(complete) != int(manifest["selection"]["expected_repositories"]):
        status = "INCOMPLETE_REMEASUREMENT"
    elif complete_nested_resolved:
        status = "MEASURED_FALSE_WARNING_RISK_REDUCTION"
    else:
        status = "NO_MEASURED_DISCOVERY_GAIN"
    return {
        "claim_boundary": manifest["claim_boundary"],
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "manifest_digest": _canonical_digest(manifest),
        "metrics": metrics,
        "observations": sorted(observations, key=lambda row: str(row["repository"])),
        "prior_status": gap_audit["status"],
        "schema_version": "aos-project-check-remeasurement/v0",
        "status": status,
        "study_id": manifest["study_id"],
    }


def collect(
    manifest_path: Path,
    gap_audit_path: Path,
    adjudication_path: Path,
    out_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    manifest = _load(manifest_path)
    gap_audit = _load(gap_audit_path)
    adjudication = _load(adjudication_path)
    if _canonical_digest(gap_audit) != manifest["source_gap_audit_digest"]:
        raise ValueError("gap audit digest does not match the frozen manifest")
    if _canonical_digest(adjudication) != manifest["source_adjudication_digest"]:
        raise ValueError("adjudication digest does not match the frozen manifest")
    labels = {
        row["repository"]: row["class"]
        for row in adjudication["labels"]
        if isinstance(row, dict)
    }
    observations = []
    source_rows = gap_audit["observations"]
    expected = int(manifest["selection"]["expected_repositories"])
    if not isinstance(source_rows, list) or len(source_rows) != expected:
        raise ValueError(f"expected {expected} frozen observations")
    for index, repository in enumerate(source_rows, 1):
        name = repository["repository"]
        response = _gh_json(
            [
                "-X",
                "GET",
                f"repos/{name}/git/trees/{repository['head_sha']}",
                "-f",
                "recursive=1",
            ]
        )
        observations.append(
            observe_tree(
                repository,
                response,
                load_blob=_github_blob_loader(name),
                adjudication=labels.get(name),
            )
        )
        print(f"project-check remeasurement {index}/{expected}", file=sys.stderr)
    result = _result(manifest, gap_audit, observations)
    _write(out_path, result)
    report_path.write_text(render(result), encoding="utf-8", newline="\n")
    return result


def _pct(value: Any) -> str:
    return "n/a" if value is None else f"{100 * float(value):.1f}%"


def render(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    return "\n".join(
        [
            "# Project Check remeasurement",
            "",
            f"Status: `{result['status']}`.",
            "",
            f"- Frozen exact-SHA repositories: **{metrics['repositories']}**.",
            f"- Complete observations: **{metrics['complete_observations']}** "
            f"({_pct(metrics['complete_observation_rate'])}).",
            "- Missing-test reasons removed by a declared nested command: "
            f"**{metrics['nested_command_resolutions']}** "
            f"({_pct(metrics['nested_command_resolution_rate'])}).",
            "- Resolutions with complete bounded nested discovery: "
            f"**{metrics['complete_nested_command_resolutions']}** "
            f"({_pct(metrics['complete_nested_command_resolution_rate'])}).",
            "- Bounded nested discovery complete: "
            f"**{metrics['bounded_discovery_complete']}/"
            f"{metrics['complete_observations']}** "
            f"({_pct(metrics['bounded_discovery_complete_rate'])}); incomplete: "
            f"**{metrics['bounded_discovery_incomplete']}**.",
            f"- Root test commands detected: **{metrics['root_commands_detected']}**.",
            "- No supported runnable command detected after bounded discovery: "
            f"**{metrics['remaining_no_supported_command']}**.",
            "- Previously adjudicated definite test surfaces with a supported "
            f"command: **{metrics['definite_surfaces_with_supported_command']}/"
            f"{metrics['definite_test_surfaces']}** "
            f"({_pct(metrics['definite_command_detection_rate'])}).",
            "- The same metric with complete bounded discovery: "
            f"**{metrics['definite_surfaces_with_complete_supported_command']}/"
            f"{metrics['definite_test_surfaces']}**.",
            "",
            "The comparison is against the frozen root-only AOS warning corpus.",
            "Only metadata and path structure were reconstructed; repository code",
            "and dependencies were not executed. A visible test file does not prove",
            "a runnable command, and this result does not measure user acceptance,",
            "retention, decision change, business severity, or superiority over",
            "another product.",
            "",
            f"Manifest: `{result['manifest_digest']}`.",
            "",
        ]
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--gap-audit", type=Path, default=DEFAULT_GAP_AUDIT)
    parser.add_argument("--adjudication", type=Path, default=DEFAULT_ADJUDICATION)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = collect(
        args.manifest,
        args.gap_audit,
        args.adjudication,
        args.out,
        args.report,
    )
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
