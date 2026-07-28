"""Auditable mass-market value study for the beginner-facing ``aos-check``.

The public-repository arm reads metadata and repository trees only. It never
checks out or executes public code. The controlled arm executes generated,
bounded fixtures to measure first-run behavior and contrast with native
command exit signals. Human adoption outcomes remain explicitly unmeasured.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from aos_workflow_gate import cli
from aos_workflow_gate.summarize import diagnose

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "benchmarks" / "mass-market" / "manifest.json"
DEFAULT_CORPUS = ROOT / "benchmarks" / "mass-market" / "corpus.json"
DEFAULT_CONTROLLED = ROOT / "benchmarks" / "mass-market" / "controlled.json"
DEFAULT_RESULTS = ROOT / "benchmarks" / "mass-market" / "results.json"
DEFAULT_REPORT = ROOT / "benchmarks" / "mass-market" / "REPORT.md"

_GRAPHQL_BATCH = 5
_GH_RETRIES = 4
_GH_TIMEOUT_SECONDS = 120


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _gh_json(arguments: list[str]) -> dict[str, Any]:
    delay = 2.0
    last_error = ""
    for attempt in range(_GH_RETRIES):
        completed = subprocess.run(
            ["gh", "api", *arguments],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=False,
            text=True,
            encoding="utf-8",
            timeout=_GH_TIMEOUT_SECONDS,
        )
        value: Any = None
        if completed.stdout.strip():
            try:
                value = json.loads(completed.stdout)
            except json.JSONDecodeError:
                pass
        if completed.returncode == 0:
            if not isinstance(value, dict):
                raise RuntimeError("GitHub API returned a non-object response")
            return value
        if isinstance(value, dict) and isinstance(value.get("data"), dict):
            # GraphQL returns useful partial data when one repository disappears
            # between Search and collection. Preserve the frozen sample as incomplete.
            return value
        last_error = " ".join(completed.stderr.split())[:500]
        if attempt + 1 < _GH_RETRIES:
            time.sleep(delay)
            delay *= 2
    raise RuntimeError(f"GitHub API failed after {_GH_RETRIES} attempts: {last_error}")


def _selection_key(seed: str, repository: str) -> str:
    return hashlib.sha256(f"{seed}\0{repository}".encode()).hexdigest()


def _search_query(language: str, star_band: str, manifest: dict[str, Any]) -> str:
    sample = manifest["sample"]
    cutoff_date = str(manifest["data_cutoff"]).split("T", 1)[0]
    return " ".join(
        (
            f"language:{language}",
            f"stars:{star_band}",
            f"pushed:>={sample['activity_filter'].split('>=', 1)[1]}",
            f"pushed:<={cutoff_date}",
            f"size:{sample['size_kib']}",
            "archived:false",
            "fork:false",
        )
    )


def _collect_selection(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    sample = manifest["sample"]
    seed = str(sample["seed"])
    bands = list(sample["star_bands"])
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for language_spec in sample["languages"]:
        language = str(language_spec["name"])
        quotas = list(language_spec["star_band_quotas"])
        for band, quota in zip(bands, quotas, strict=True):
            query = _search_query(language, str(band), manifest)
            response = _gh_json(
                [
                    "-X",
                    "GET",
                    "search/repositories",
                    "-f",
                    f"q={query}",
                    "-f",
                    "per_page=100",
                    "-f",
                    "sort=updated",
                    "-f",
                    "order=desc",
                ]
            )
            items = response.get("items")
            if not isinstance(items, list):
                raise RuntimeError(f"search returned no item list for {query}")
            candidates = sorted(
                (item for item in items if isinstance(item, dict)),
                key=lambda item: _selection_key(seed, str(item.get("full_name"))),
            )
            chosen = []
            for item in candidates:
                full_name = item.get("full_name")
                if not isinstance(full_name, str) or full_name in seen:
                    continue
                default_branch = item.get("default_branch")
                if not isinstance(default_branch, str) or not default_branch:
                    continue
                seen.add(full_name)
                chosen.append(
                    {
                        "default_branch": default_branch,
                        "forks": int(item.get("forks_count") or 0),
                        "github_primary_language": item.get("language"),
                        "html_url": item.get("html_url"),
                        "license": (
                            item.get("license", {}).get("spdx_id")
                            if isinstance(item.get("license"), dict)
                            else None
                        ),
                        "open_issues": int(item.get("open_issues_count") or 0),
                        "pushed_at": item.get("pushed_at"),
                        "repository": full_name,
                        "search_language": language,
                        "selection_key": _selection_key(seed, full_name),
                        "size_kib": int(item.get("size") or 0),
                        "star_band": band,
                        "stars": int(item.get("stargazers_count") or 0),
                    }
                )
                if len(chosen) == int(quota):
                    break
            if len(chosen) != int(quota):
                raise RuntimeError(
                    f"stratum {language}/{band} yielded {len(chosen)}, needs {quota}"
                )
            selected.extend(chosen)
            print(f"selected {language}/{band}: {len(chosen)}", file=sys.stderr)
    expected = int(sample["target_repositories"])
    if len(selected) != expected:
        raise RuntimeError(
            f"selected {len(selected)} repositories, expected {expected}"
        )
    return selected


def _gql(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _object_field(alias: str, branch: str, path: str, *, tree: bool) -> str:
    expression = f"{branch}:{path}"
    if tree:
        projection = "... on Tree { oid entries { name type oid } }"
    else:
        projection = "... on Blob { oid byteSize text }"
    return f"{alias}: object(expression: {_gql(expression)}) {{ {projection} }}"


def _repository_query(alias: str, item: dict[str, Any]) -> str:
    owner, name = str(item["repository"]).split("/", 1)
    branch = str(item["default_branch"])
    blob_paths = {
        "build_gradle": "build.gradle",
        "build_gradle_kts": "build.gradle.kts",
        "bun_lock": "bun.lock",
        "bun_lockb": "bun.lockb",
        "cargo_toml": "Cargo.toml",
        "go_mod": "go.mod",
        "gradlew": "gradlew",
        "gradlew_bat": "gradlew.bat",
        "package": "package.json",
        "package_lock": "package-lock.json",
        "pnpm_lock": "pnpm-lock.yaml",
        "pom_xml": "pom.xml",
        "pyproject": "pyproject.toml",
        "pytest_ini": "pytest.ini",
        "setup_cfg": "setup.cfg",
        "setup_py": "setup.py",
        "tox_ini": "tox.ini",
        "yarn_lock": "yarn.lock",
    }
    fields = [
        "defaultBranchRef { name target { ... on Commit { oid } } }",
        _object_field("root", branch, "", tree=True),
        _object_field("src", branch, "src", tree=True),
        _object_field("test_dir", branch, "test", tree=True),
        _object_field("tests_dir", branch, "tests", tree=True),
    ]
    fields.extend(
        _object_field(field, branch, path, tree=False)
        for field, path in blob_paths.items()
    )
    return (
        f"{alias}: repository(owner: {_gql(owner)}, name: {_gql(name)}) "
        "{ " + " ".join(fields) + " }"
    )


def _batch_observations(
    items: list[dict[str, Any]],
) -> tuple[list[Any], dict[str, Any]]:
    fields = [_repository_query(f"r{index}", item) for index, item in enumerate(items)]
    query = "query { " + " ".join(fields) + " rateLimit { cost remaining resetAt } }"
    response = _gh_json(["graphql", "-f", f"query={query}"])
    data = response.get("data")
    if not isinstance(data, dict):
        raise RuntimeError(f"GraphQL response has no data: {response.get('errors')}")
    return [data.get(f"r{index}") for index in range(len(items))], dict(
        data.get("rateLimit") or {}
    )


def _blob(value: Any) -> dict[str, Any] | None:
    return value if isinstance(value, dict) else None


def _tree_entries(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    entries = value.get("entries")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _tree_may_contain_python(value: Any) -> bool:
    return any(
        str(entry.get("name", "")).lower().endswith(".py")
        or entry.get("type") == "tree"
        for entry in _tree_entries(value)
    )


def _derive_observation(item: dict[str, Any], raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {**item, "collection_error": "repository_unavailable", "complete": False}
    default_ref = raw.get("defaultBranchRef")
    target = default_ref.get("target") if isinstance(default_ref, dict) else None
    head_sha = target.get("oid") if isinstance(target, dict) else None
    root_entries = _tree_entries(raw.get("root"))
    root_names = sorted(str(entry.get("name")) for entry in root_entries)
    root_truncation_risk = len(root_entries) >= 100

    package = _blob(raw.get("package"))
    package_text = package.get("text") if package else None
    scripts: dict[str, str] = {}
    package_error: str | None = None
    dependencies_declared = False
    if isinstance(package_text, str):
        try:
            package_json = json.loads(package_text)
            raw_scripts = (
                package_json.get("scripts") if isinstance(package_json, dict) else None
            )
            if isinstance(raw_scripts, dict):
                scripts = {
                    str(name): value
                    for name, value in raw_scripts.items()
                    if isinstance(value, str) and value.strip()
                }
            dependencies_declared = isinstance(package_json, dict) and any(
                isinstance(package_json.get(field), dict) and package_json[field]
                for field in ("dependencies", "devDependencies", "peerDependencies")
            )
        except json.JSONDecodeError:
            package_error = "malformed_package_json"
    elif package is not None:
        package_error = "package_text_unavailable"

    pyproject = _blob(raw.get("pyproject"))
    pyproject_text = pyproject.get("text") if pyproject else None
    root_python = any(name.lower().endswith(".py") for name in root_names)
    src_python = _tree_may_contain_python(raw.get("src")) and (
        item.get("search_language") == "Python"
        or item.get("github_primary_language") == "Python"
    )
    python = (
        any(
            raw.get(field) is not None
            for field in ("pyproject", "setup_py", "setup_cfg")
        )
        or root_python
        or src_python
    )
    python_tests = python and (
        any(raw.get(field) is not None for field in ("pytest_ini", "tox_ini"))
        or any(
            name.lower().startswith("test_")
            and name.lower().endswith(".py")
            or name.lower().endswith("_test.py")
            for name in root_names
        )
        or _tree_may_contain_python(raw.get("test_dir"))
        or _tree_may_contain_python(raw.get("tests_dir"))
        or (isinstance(pyproject_text, str) and "[tool.pytest" in pyproject_text)
    )

    ecosystems: list[str] = []
    checks: list[dict[str, str]] = []
    if python:
        ecosystems.append("Python")
        checks.append({"category": "build", "id": "python.compile"})
        if python_tests:
            checks.append({"category": "test", "id": "python.tests"})
    if package is not None:
        ecosystems.append("Node.js")
        for name, category in (
            ("build", "build"),
            ("typecheck", "build"),
            ("test", "test"),
            ("lint", "quality"),
        ):
            value = scripts.get(name)
            if value and not (name == "test" and "no test specified" in value.lower()):
                checks.append({"category": category, "id": f"node.{name}"})
    for field, ecosystem, check_id in (
        ("go_mod", "Go", "go.tests"),
        ("cargo_toml", "Rust", "rust.tests"),
        ("pom_xml", "Java/Maven", "maven.tests"),
    ):
        if raw.get(field) is not None:
            ecosystems.append(ecosystem)
            checks.append({"category": "test", "id": check_id})
    if raw.get("gradlew") is not None or raw.get("gradlew_bat") is not None:
        ecosystems.append("Java/Gradle")
        checks.append({"category": "test", "id": "gradle.tests"})

    ecosystems = list(dict.fromkeys(ecosystems))
    behavioral = any(check["category"] == "test" for check in checks)
    supported = bool(ecosystems)
    non_test_surface = any(check["category"] != "test" for check in checks)
    incomplete = raw.get("root") is None or root_truncation_risk
    limitations = []
    if not supported:
        limitations.append("unsupported_root_project")
    if supported and not behavioral:
        limitations.append("no_behavioral_test_surface")
    if package_error:
        limitations.append(package_error)
    if root_truncation_risk:
        limitations.append("root_tree_may_be_truncated")

    relevant_blobs = {}
    for field in (
        "cargo_toml",
        "go_mod",
        "package",
        "pom_xml",
        "pyproject",
        "setup_cfg",
        "setup_py",
    ):
        blob = _blob(raw.get(field))
        if blob is not None:
            relevant_blobs[field] = {
                "bytes": blob.get("byteSize"),
                "oid": blob.get("oid"),
            }

    return {
        **item,
        "behavioral_surface": behavioral,
        "checks": checks,
        "complete": not incomplete,
        "coverage_gap_candidate": supported and not behavioral and non_test_surface,
        "dependencies_declared": dependencies_declared,
        "ecosystems": ecosystems,
        "head_sha": head_sha,
        "limitations": limitations,
        "package_manager": (
            "pnpm"
            if raw.get("pnpm_lock") is not None
            else "yarn"
            if raw.get("yarn_lock") is not None
            else "bun"
            if raw.get("bun_lock") is not None or raw.get("bun_lockb") is not None
            else "npm"
            if package is not None
            else None
        ),
        "relevant_blobs": relevant_blobs,
        "root_entry_count": len(root_entries),
        "root_tree_oid": raw.get("root", {}).get("oid")
        if isinstance(raw.get("root"), dict)
        else None,
        "supported": supported,
        "verdict_proxy": "PASS"
        if supported and behavioral and not incomplete
        else "WARN",
        "wrapper_only_candidate": supported and behavioral,
    }


def collect(manifest_path: Path, out_path: Path) -> dict[str, Any]:
    manifest = _load(manifest_path)
    if manifest.get("schema_version") != "aos-mass-value-study/v0":
        raise ValueError("unsupported study manifest")
    selected = _collect_selection(manifest)
    observed: list[dict[str, Any]] = []
    last_rate: dict[str, Any] = {}
    for offset in range(0, len(selected), _GRAPHQL_BATCH):
        batch = selected[offset : offset + _GRAPHQL_BATCH]
        raw_values, last_rate = _batch_observations(batch)
        observed.extend(
            _derive_observation(item, raw)
            for item, raw in zip(batch, raw_values, strict=True)
        )
        print(f"observed {len(observed)}/{len(selected)}", file=sys.stderr)
    corpus = {
        "boundary": manifest["claim_boundary"],
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "github_rate_limit_after_collection": last_rate,
        "manifest_digest": _canonical_digest(manifest),
        "repositories": observed,
        "sample_digest": _canonical_digest(
            [
                {
                    "head_sha": item.get("head_sha"),
                    "repository": item["repository"],
                    "selection_key": item["selection_key"],
                }
                for item in observed
            ]
        ),
        "schema_version": "aos-mass-repository-corpus/v0",
        "study_id": manifest["study_id"],
    }
    _write(out_path, corpus)
    return corpus


def _fixture_python(root: Path, *, test: str | None) -> None:
    (root / "pyproject.toml").write_text(
        '[project]\nname = "fixture"\nversion = "0.0.0"\n',
        encoding="utf-8",
    )
    (root / "app.py").write_text("def answer():\n    return 2\n", encoding="utf-8")
    if test is not None:
        tests = root / "tests"
        tests.mkdir()
        (tests / "test_app.py").write_text(test, encoding="utf-8")


def _fixture_node(root: Path, scripts: dict[str, str], *, package_manager: str) -> None:
    (root / "package.json").write_text(
        json.dumps({"name": "fixture", "private": True, "scripts": scripts}) + "\n",
        encoding="utf-8",
    )
    manager_lock = {
        "bun": "bun.lock",
        "pnpm": "pnpm-lock.yaml",
        "yarn": "yarn.lock",
    }.get(package_manager)
    if manager_lock:
        (root / manager_lock).write_text("# controlled fixture\n", encoding="utf-8")


def _controlled_specs(root: Path) -> list[tuple[str, Path, str | None]]:
    specs: list[tuple[str, Path, str | None]] = []

    python_pass = root / "python_pass"
    python_pass.mkdir()
    _fixture_python(
        python_pass,
        test="from app import answer\n\ndef test_answer():\n    assert answer() == 2\n",
    )
    specs.append(("python_pass", python_pass, None))

    python_no_test = root / "python_no_test"
    python_no_test.mkdir()
    _fixture_python(python_no_test, test=None)
    specs.append(("python_no_test", python_no_test, None))

    secret = "AOS-CONTROLLED-SECRET"
    python_secret = root / "python_secret_failure"
    python_secret.mkdir()
    _fixture_python(
        python_secret,
        test=(f"def test_failure():\n    print({secret!r})\n    assert False\n"),
    )
    specs.append(("python_secret_failure", python_secret, secret))

    unknown = root / "unknown_project"
    unknown.mkdir()
    (unknown / "README.txt").write_text("unknown fixture\n", encoding="utf-8")
    specs.append(("unknown_project", unknown, None))

    malformed = root / "malformed_node_manifest"
    malformed.mkdir()
    (malformed / "package.json").write_text("{not-json\n", encoding="utf-8")
    specs.append(("malformed_node_manifest", malformed, None))

    package_manager = next(
        (name for name in ("npm", "pnpm", "yarn", "bun") if shutil.which(name)), None
    )
    if shutil.which("node") and package_manager:
        node_cases = {
            "node_pass": {
                "build": 'node -e "process.exit(0)"',
                "test": 'node -e "process.exit(0)"',
            },
            "node_no_test": {"build": 'node -e "process.exit(0)"'},
            "node_lint_warning": {
                "test": 'node -e "process.exit(0)"',
                "lint": 'node -e "process.exit(1)"',
            },
            "node_test_failure": {"test": 'node -e "process.exit(1)"'},
        }
        for case_id, scripts in node_cases.items():
            path = root / case_id
            path.mkdir()
            _fixture_node(path, scripts, package_manager=package_manager)
            specs.append((case_id, path, None))
    return specs


def controlled(manifest_path: Path, out_path: Path) -> dict[str, Any]:
    manifest = _load(manifest_path)
    expected = {
        "malformed_node_manifest": "WARN",
        "node_lint_warning": "WARN",
        "node_no_test": "WARN",
        "node_pass": "PASS",
        "node_test_failure": "BLOCK",
        "python_no_test": "WARN",
        "python_pass": "PASS",
        "python_secret_failure": "BLOCK",
        "unknown_project": "WARN",
    }
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="aos-mass-controlled-") as raw_root:
        root = Path(raw_root)
        evidence_root = root / "evidence"
        fixture_root = root / "fixtures"
        evidence_root.mkdir()
        fixture_root.mkdir()
        for case_id, project, secret in _controlled_specs(fixture_root):
            case_evidence = evidence_root / case_id
            paths = {
                "source": case_evidence / "source.json",
                "bundle": case_evidence / "bundle.json",
                "policy": case_evidence / "policy.json",
                "record": case_evidence / "record.json",
            }
            stdout = io.StringIO()
            stderr = io.StringIO()
            started = time.monotonic()
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                exit_code = cli.main(
                    [
                        "check-project",
                        str(project),
                        "--source-out",
                        str(paths["source"]),
                        "--bundle-out",
                        str(paths["bundle"]),
                        "--policy-out",
                        str(paths["policy"]),
                        "--out",
                        str(paths["record"]),
                        "--timeout-seconds",
                        "30",
                    ]
                )
            elapsed_ms = int((time.monotonic() - started) * 1000)
            source = _load(paths["source"])
            record = _load(paths["record"])
            diagnosis = diagnose(record)
            identity = source.get("identity")
            checks = identity.get("checks", []) if isinstance(identity, dict) else []
            evidence_text = "\n".join(
                path.read_text(encoding="utf-8") for path in paths.values()
            )
            native_failure = any(
                isinstance(check, dict) and check.get("state") == "failed"
                for check in checks
            )
            check_elapsed = sum(
                int(check.get("elapsed_ms") or 0)
                for check in checks
                if isinstance(check, dict)
            )
            reason_rules = [
                str(reason.get("rule"))
                for reason in record.get("reasons", [])
                if isinstance(reason, dict)
                and reason.get("severity") in {"WARN", "BLOCK"}
            ]
            supported = (
                bool(identity.get("ecosystems"))
                if isinstance(identity, dict)
                else False
            )
            actionable_proxy = (
                supported
                and "project_verification_limited" in reason_rules
                and "behavioral test" in str(source.get("summary", "")).lower()
            )
            rows.append(
                {
                    "actionable_coverage_gap_proxy": actionable_proxy,
                    "aos_incremental_contrast": (
                        record.get("verdict") != "PASS" and not native_failure
                    ),
                    "case_id": case_id,
                    "check_elapsed_ms": check_elapsed,
                    "checks": len(checks),
                    "elapsed_ms": elapsed_ms,
                    "evidence_contains_project_path": str(project) in evidence_text,
                    "exit_code": exit_code,
                    "expected_verdict": expected[case_id],
                    "finding_words": len(str(diagnosis.get("finding", "")).split()),
                    "native_failure_signal": native_failure,
                    "next_action_present": bool(str(diagnosis.get("next", "")).strip()),
                    "next_words": len(str(diagnosis.get("next", "")).split()),
                    "no_git": not (project / ".git").exists(),
                    "output_words": len(stdout.getvalue().split()),
                    "overhead_ms": max(0, elapsed_ms - check_elapsed),
                    "raw_secret_absent_from_evidence": (
                        secret is None or secret not in evidence_text
                    ),
                    "reason_rules": reason_rules,
                    "verdict": record.get("verdict"),
                }
            )
    missing = sorted(
        set(manifest["controlled_execution"]["cases"]) - {r["case_id"] for r in rows}
    )
    complete = not missing
    elapsed = [int(row["elapsed_ms"]) for row in rows]
    nonpass = [row for row in rows if row["verdict"] != "PASS"]
    result = {
        "boundary": manifest["controlled_execution"]["scope"],
        "cases": sorted(rows, key=lambda row: str(row["case_id"])),
        "manifest_digest": _canonical_digest(manifest),
        "metrics": {
            "actionable_coverage_gap_proxy_rate": _rate(
                sum(bool(row["actionable_coverage_gap_proxy"]) for row in rows),
                len(rows),
            ),
            "cases_completed": len(rows),
            "cases_preregistered": len(manifest["controlled_execution"]["cases"]),
            "evidence_hygiene_rate": _rate(
                sum(
                    not row["evidence_contains_project_path"]
                    and row["raw_secret_absent_from_evidence"]
                    for row in rows
                ),
                len(rows),
            ),
            "incremental_contrast_rate": _rate(
                sum(bool(row["aos_incremental_contrast"]) for row in rows), len(rows)
            ),
            "median_elapsed_ms": statistics.median(elapsed) if elapsed else None,
            "missing_cases": missing,
            "named_next_rate_nonpass": _rate(
                sum(bool(row["next_action_present"]) for row in nonpass), len(nonpass)
            ),
            "p95_elapsed_ms": _percentile(elapsed, 0.95),
            "verdict_accuracy_rate": _rate(
                sum(row["verdict"] == row["expected_verdict"] for row in rows),
                len(rows),
            ),
        },
        "schema_version": "aos-mass-controlled-results/v0",
        "status": "COMPLETE" if complete else "INCOMPLETE",
        "study_id": manifest["study_id"],
    }
    _write(out_path, result)
    return result


def _rate(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 4) if denominator else None


def _wilson(successes: int, total: int) -> dict[str, float | None]:
    if total == 0:
        return {"lower": None, "point": None, "upper": None}
    z = 1.959963984540054
    point = successes / total
    denominator = 1 + z * z / total
    center = (point + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(point * (1 - point) / total + z * z / (4 * total * total))
        / denominator
    )
    return {
        "lower": round(max(0.0, center - margin), 4),
        "point": round(point, 4),
        "upper": round(min(1.0, center + margin), 4),
    }


def _percentile(values: Iterable[int], quantile: float) -> int | None:
    ordered = sorted(values)
    if not ordered:
        return None
    index = math.ceil(quantile * len(ordered)) - 1
    return ordered[max(0, min(index, len(ordered) - 1))]


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    detected = sum(bool(row.get("supported")) for row in rows)
    behavioral = sum(bool(row.get("behavioral_surface")) for row in rows)
    complete = sum(bool(row.get("complete")) for row in rows)
    gaps = sum(bool(row.get("coverage_gap_candidate")) for row in rows)
    wrappers = sum(bool(row.get("wrapper_only_candidate")) for row in rows)
    return {
        "behavioral_surface": behavioral,
        "behavioral_surface_rate": _rate(behavioral, total),
        "complete": complete,
        "coverage_gap_candidates": gaps,
        "coverage_gap_candidate_rate": _rate(gaps, total),
        "detected": detected,
        "detection_rate": _rate(detected, total),
        "detection_wilson_95": _wilson(detected, total),
        "incomplete": total - complete,
        "incomplete_rate": _rate(total - complete, total),
        "repositories": total,
        "wrapper_only_candidates": wrappers,
        "wrapper_only_candidate_rate": _rate(wrappers, total),
    }


def analyze(
    manifest_path: Path,
    corpus_path: Path,
    controlled_path: Path,
    out_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    manifest = _load(manifest_path)
    corpus = _load(corpus_path)
    controlled_result = _load(controlled_path)
    if corpus.get("manifest_digest") != _canonical_digest(manifest):
        raise ValueError("corpus is not bound to the supplied manifest")
    if controlled_result.get("manifest_digest") != _canonical_digest(manifest):
        raise ValueError("controlled results are not bound to the supplied manifest")
    rows = corpus.get("repositories")
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        raise ValueError("corpus repositories are malformed")
    typed_rows: list[dict[str, Any]] = list(rows)
    overall = _aggregate(typed_rows)
    by_language = {}
    for language in [spec["name"] for spec in manifest["sample"]["languages"]]:
        by_language[str(language)] = _aggregate(
            [row for row in typed_rows if row.get("search_language") == language]
        )
    by_star_band = {}
    for band in manifest["sample"]["star_bands"]:
        by_star_band[str(band)] = _aggregate(
            [row for row in typed_rows if row.get("star_band") == band]
        )
    ecosystem_gaps = sorted(
        {
            str(row.get("search_language"))
            for row in typed_rows
            if row.get("coverage_gap_candidate")
        }
    )
    thresholds = manifest["technical_thresholds"]
    technical_checks = {
        "behavioral_surface_rate": bool(
            overall["behavioral_surface_rate"] is not None
            and overall["behavioral_surface_rate"]
            >= thresholds["behavioral_surface_rate_min"]
        ),
        "coverage_gap_candidate_ecosystems": len(ecosystem_gaps)
        >= thresholds["coverage_gap_candidate_ecosystems_min"],
        "coverage_gap_candidate_rate": bool(
            overall["coverage_gap_candidate_rate"] is not None
            and overall["coverage_gap_candidate_rate"]
            >= thresholds["coverage_gap_candidate_rate_min"]
        ),
        "incomplete_observation_rate": bool(
            overall["incomplete_rate"] is not None
            and overall["incomplete_rate"]
            <= thresholds["incomplete_observation_rate_max"]
        ),
        "per_language_detection_rate": all(
            value["detection_rate"] is not None
            and value["detection_rate"] >= thresholds["per_language_detection_rate_min"]
            for value in by_language.values()
        ),
        "static_detection_wilson_lower": bool(
            overall["detection_wilson_95"]["lower"] is not None
            and overall["detection_wilson_95"]["lower"]
            >= thresholds["static_detection_wilson_lower_min"]
        ),
    }
    controlled_metrics = controlled_result["metrics"]
    controlled_ready = (
        controlled_result.get("status") == "COMPLETE"
        and controlled_metrics.get("verdict_accuracy_rate") == 1.0
        and controlled_metrics.get("named_next_rate_nonpass") == 1.0
        and controlled_metrics.get("evidence_hygiene_rate") == 1.0
    )
    technical_ready = all(technical_checks.values()) and controlled_ready
    results = {
        "boundary": manifest["claim_boundary"],
        "controlled": controlled_metrics,
        "corpus_digest": _canonical_digest(corpus),
        "coverage_gap_candidate_ecosystems": ecosystem_gaps,
        "external_metrics": {
            key: {"required_threshold": value, "value": None}
            for key, value in manifest["external_metrics_required"].items()
        },
        "manifest_digest": _canonical_digest(manifest),
        "mass_market_status": "NO_GO_EXTERNAL_VALIDATION_REQUIRED",
        "metrics": {
            "by_language": by_language,
            "by_star_band": by_star_band,
            "ecosystems_detected": dict(
                sorted(
                    Counter(
                        ecosystem
                        for row in typed_rows
                        for ecosystem in row.get("ecosystems", [])
                    ).items()
                )
            ),
            "limitations": dict(
                sorted(
                    Counter(
                        limitation
                        for row in typed_rows
                        for limitation in row.get("limitations", [])
                    ).items()
                )
            ),
            "overall": overall,
            "verdict_proxy": dict(
                sorted(
                    Counter(str(row.get("verdict_proxy")) for row in typed_rows).items()
                )
            ),
        },
        "schema_version": "aos-mass-value-results/v0",
        "study_id": manifest["study_id"],
        "technical_checks": technical_checks,
        "technical_distribution_status": (
            "TECHNICAL_DISTRIBUTION_READY"
            if technical_ready
            else "TECHNICAL_DISTRIBUTION_NOT_READY"
        ),
        "validation_offer_status": (
            "FREE_PREVIEW_TESTABLE" if controlled_ready else "PREVIEW_NOT_READY"
        ),
    }
    _write(out_path, results)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_report(manifest, corpus, controlled_result, results),
        encoding="utf-8",
        newline="\n",
    )
    return results


def _pct(value: Any) -> str:
    return "n/a" if value is None else f"{100 * float(value):.1f}%"


def render_report(
    manifest: dict[str, Any],
    corpus: dict[str, Any],
    controlled_result: dict[str, Any],
    results: dict[str, Any],
) -> str:
    overall = results["metrics"]["overall"]
    lines = [
        "# AOS Check mass-market value study",
        "",
        f"Status: `{results['mass_market_status']}`.",
        f"Technical distribution: `{results['technical_distribution_status']}`.",
        f"Free preview: `{results['validation_offer_status']}`.",
        "",
        "## Claim boundary",
        "",
        str(manifest["claim_boundary"]),
        "",
        "Public repository code was not executed. The repository arm reads public",
        "metadata, root manifests, and tree shape at an exact commit. Controlled",
        "execution uses generated fixtures only.",
        "",
        "## Repository corpus",
        "",
        f"- Repositories: **{overall['repositories']}**.",
        f"- Static detection: **{_pct(overall['detection_rate'])}**; Wilson 95% CI "
        f"**{_pct(overall['detection_wilson_95']['lower'])} to "
        f"{_pct(overall['detection_wilson_95']['upper'])}**.",
        "- Discoverable behavioral surface: "
        f"**{_pct(overall['behavioral_surface_rate'])}**.",
        "- Coverage-gap candidates: "
        f"**{_pct(overall['coverage_gap_candidate_rate'])}**.",
        "- Wrapper-only candidates: "
        f"**{_pct(overall['wrapper_only_candidate_rate'])}**.",
        f"- Incomplete observations: **{_pct(overall['incomplete_rate'])}**.",
        "",
        "| Search language | Repos | Detection | Behavioral surface | "
        "Gap candidate | Incomplete |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for language, value in results["metrics"]["by_language"].items():
        lines.append(
            f"| {language} | {value['repositories']} | "
            f"{_pct(value['detection_rate'])} | "
            f"{_pct(value['behavioral_surface_rate'])} | "
            f"{_pct(value['coverage_gap_candidate_rate'])} | "
            f"{_pct(value['incomplete_rate'])} |"
        )
    controlled_metrics = controlled_result["metrics"]
    lines += [
        "",
        "## Controlled first run",
        "",
        f"- Cases: **{controlled_metrics['cases_completed']}**/"
        f"**{controlled_metrics['cases_preregistered']}**.",
        "- Expected verdict accuracy: "
        f"**{_pct(controlled_metrics['verdict_accuracy_rate'])}**.",
        "- Named Next on non-PASS: "
        f"**{_pct(controlled_metrics['named_next_rate_nonpass'])}**.",
        f"- Evidence hygiene: **{_pct(controlled_metrics['evidence_hygiene_rate'])}**.",
        f"- Median result time: **{controlled_metrics['median_elapsed_ms']} ms**; "
        f"p95 **{controlled_metrics['p95_elapsed_ms']} ms**.",
        f"- Contrast beyond native nonzero exit: "
        f"**{_pct(controlled_metrics['incremental_contrast_rate'])}**.",
        f"- Actionable coverage-gap proxy: "
        f"**{_pct(controlled_metrics['actionable_coverage_gap_proxy_rate'])}**.",
        "",
        "The contrast metric is not a defect-detection lift. In v0, AOS mostly",
        "orchestrates existing checks and adds a warning when behavioral evidence",
        "is absent. Business importance is not established by this proxy.",
        "",
        "## Comparator boundary",
        "",
        "| Product | No Git path | Runs behavioral checks | Detects absent test "
        "surface | Finds new code issues | Replayable local decision |",
        "| --- | --- | --- | --- | --- | --- |",
        "| AOS Check v0 | yes | existing project checks | yes | no | yes |",
        "| Native pytest/npm scripts | yes | yes | no aggregate warning | "
        "only their own checks | no |",
        "| pre-commit | no; Git hook/config centered | configured hooks | no | "
        "hook-dependent | no |",
        "| GitHub Actions | no; repository workflow | configured jobs | no | "
        "job-dependent | artifacts/checks |",
        "| MegaLinter | local Docker/Node path | primarily linting | no | "
        "linter findings | reports, not AOS replay |",
        "| Copilot code review | PR/account path | may use agentic tools | no "
        "deterministic contract | yes, probabilistic | no AOS-style record |",
        "| SonarQube Cloud | Git/PR/service path | analysis, coverage input | "
        "coverage-dependent | yes | service history |",
        "",
        "The matrix compares documented activation and output categories, not",
        "precision or efficacy. No cross-product defect benchmark was run.",
        "",
        "## External outcomes still required",
        "",
    ]
    for metric, spec in results["external_metrics"].items():
        lines.append(
            f"- `{metric}`: unmeasured; threshold `{spec['required_threshold']}`."
        )
    lines += [
        "",
        "Until these outcomes are observed, the only justified distribution is a",
        "free advisory preview. A paid or broad correctness claim remains `NO_GO`.",
        "",
        "## Sources",
        "",
        "- [pytest invocation](https://docs.pytest.org/en/stable/how-to/usage.html)",
        "- [pre-commit configuration and Git hooks](https://pre-commit.com/)",
        "- [GitHub Actions workflows](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflows)",
        "- [MegaLinter local runner](https://megalinter.io/latest/mega-linter-runner/)",
        "- [GitHub Copilot code review](https://docs.github.com/en/copilot/concepts/agents/code-review)",
        "- [SonarQube Cloud pull request analysis](https://docs.sonarsource.com/sonarqube-cloud/improving/pull-request-analysis)",
        "- [Stack Overflow 2025 AI survey](https://survey.stackoverflow.co/2025/ai)",
        "- [DORA 2025 AI-assisted development](https://dora.dev/research/2025/dora-report/)",
        "",
        "## Integrity",
        "",
        f"- Manifest digest: `{results['manifest_digest']}`.",
        f"- Corpus digest: `{results['corpus_digest']}`.",
        f"- Sample digest: `{corpus['sample_digest']}`.",
        "",
    ]
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("collect", "controlled", "analyze", "all"):
        child = subparsers.add_parser(command)
        child.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
        child.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
        child.add_argument("--controlled", type=Path, default=DEFAULT_CONTROLLED)
        child.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
        child.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command in {"collect", "all"}:
        collect(args.manifest, args.corpus)
    if args.command in {"controlled", "all"}:
        controlled(args.manifest, args.controlled)
    if args.command in {"analyze", "all"}:
        result = analyze(
            args.manifest,
            args.corpus,
            args.controlled,
            args.results,
            args.report,
        )
        print(result["mass_market_status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
