"""Audit every missing-test-surface candidate against exact-SHA tree paths."""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from tools.mass_value_study import _canonical_digest, _gh_json, _load, _rate, _write

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "benchmarks" / "mass-market" / "gap-audit-manifest.json"
DEFAULT_CORPUS = ROOT / "benchmarks" / "mass-market" / "corpus.json"
DEFAULT_OUT = ROOT / "benchmarks" / "mass-market" / "gap-audit.json"
DEFAULT_REPORT = ROOT / "benchmarks" / "mass-market" / "GAP_AUDIT.md"


def _excluded(path: str, manifest: dict[str, Any]) -> bool:
    segments = {segment for segment in path.lower().split("/") if segment}
    return any(
        str(excluded).lower() in segments
        for excluded in manifest["excluded_path_segments"]
    )


def is_test_path(path: str, manifest: dict[str, Any]) -> bool:
    lowered = path.lower().replace("\\", "/").strip("/")
    if not lowered or _excluded(lowered, manifest):
        return False
    segments = lowered.split("/")
    name = segments[-1]
    if name in {str(item).lower() for item in manifest["test_config_names"]}:
        return True
    if any(
        segment in {"test", "tests", "__tests__", "spec", "specs"}
        for segment in segments[:-1]
    ):
        return True
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or name.endswith("_test.go")
        or ".test." in name
        or ".spec." in name
    )


def _observe(
    repository: dict[str, Any], response: dict[str, Any], manifest: dict[str, Any]
) -> dict[str, Any]:
    tree = response.get("tree")
    entries = tree if isinstance(tree, list) else []
    paths = sorted(
        str(entry.get("path"))
        for entry in entries
        if isinstance(entry, dict)
        and entry.get("type") == "blob"
        and isinstance(entry.get("path"), str)
    )
    test_paths = [path for path in paths if is_test_path(path, manifest)]
    truncated = response.get("truncated") is True
    if truncated:
        classification = "inconclusive"
    elif test_paths:
        classification = "contradicted_by_paths"
    else:
        classification = "supported_missing_surface"
    nested_manifests = [
        path
        for path in paths
        if "/" in path
        and path.rsplit("/", 1)[-1]
        in {
            "Cargo.toml",
            "build.gradle",
            "build.gradle.kts",
            "go.mod",
            "package.json",
            "pom.xml",
            "pyproject.toml",
        }
    ]
    workflows = [
        path
        for path in paths
        if path.startswith(".github/workflows/")
        and path.lower().endswith((".yaml", ".yml"))
    ]
    return {
        "classification": classification,
        "complete": not truncated,
        "head_sha": repository["head_sha"],
        "nested_manifest_count": len(nested_manifests),
        "repository": repository["repository"],
        "search_language": repository["search_language"],
        "star_band": repository["star_band"],
        "test_path_count": len(test_paths),
        "test_path_examples": test_paths[:10],
        "tree_entries": len(entries),
        "tree_truncated": truncated,
        "workflow_count": len(workflows),
    }


def collect(
    manifest_path: Path,
    corpus_path: Path,
    out_path: Path,
    report_path: Path,
) -> dict[str, Any]:
    manifest = _load(manifest_path)
    corpus = _load(corpus_path)
    if corpus.get("sample_digest") != manifest["source_corpus_sample_digest"]:
        raise ValueError("source corpus digest does not match gap audit manifest")
    repositories = [
        row
        for row in corpus["repositories"]
        if isinstance(row, dict) and row.get("coverage_gap_candidate") is True
    ]
    expected = int(manifest["selection"]["expected_repositories"])
    if len(repositories) != expected:
        raise ValueError(
            f"selected {len(repositories)} candidates, expected {expected}"
        )
    observations = []
    for index, repository in enumerate(repositories, 1):
        response = _gh_json(
            [
                "-X",
                "GET",
                f"repos/{repository['repository']}/git/trees/{repository['head_sha']}",
                "-f",
                "recursive=1",
            ]
        )
        observations.append(_observe(repository, response, manifest))
        print(f"gap audit {index}/{len(repositories)}", file=sys.stderr)
    result = _result(manifest, corpus, observations)
    _write(out_path, result)
    report_path.write_text(render(result), encoding="utf-8", newline="\n")
    return result


def _result(
    manifest: dict[str, Any],
    corpus: dict[str, Any],
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    total = len(observations)
    counts = Counter(str(row["classification"]) for row in observations)
    complete = total - counts["inconclusive"]
    contradicted = counts["contradicted_by_paths"]
    supported = counts["supported_missing_surface"]
    metrics = {
        "complete_observation_rate": _rate(complete, total),
        "contradiction_rate": _rate(contradicted, complete),
        "contradicted_by_paths": contradicted,
        "inconclusive": counts["inconclusive"],
        "repositories": total,
        "supported_missing_surface": supported,
        "supported_missing_surface_rate": _rate(supported, complete),
    }
    thresholds = manifest["thresholds"]
    checks = {
        "complete": metrics["complete_observation_rate"]
        >= thresholds["complete_observation_rate_min"],
        "contradiction": metrics["contradiction_rate"]
        <= thresholds["contradiction_rate_max"],
        "supported": metrics["supported_missing_surface_rate"]
        >= thresholds["supported_missing_surface_rate_min"],
    }
    if not checks["complete"]:
        status = "INSUFFICIENT_PATH_EVIDENCE"
    elif checks["contradiction"] and checks["supported"]:
        status = "LOW_NOISE_PATH_PROXY"
    else:
        status = "HIGH_FALSE_POSITIVE_RISK"
    return {
        "by_language": {
            language: dict(
                sorted(
                    Counter(
                        str(row["classification"])
                        for row in observations
                        if row["search_language"] == language
                    ).items()
                )
            )
            for language in sorted(
                {str(row["search_language"]) for row in observations}
            )
        },
        "collected_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "corpus_digest": _canonical_digest(corpus),
        "manifest_digest": _canonical_digest(manifest),
        "metrics": metrics,
        "observations": sorted(observations, key=lambda row: str(row["repository"])),
        "schema_version": "aos-mass-gap-audit-result/v0",
        "status": status,
        "study_id": manifest["study_id"],
        "threshold_checks": checks,
    }


def _pct(value: Any) -> str:
    return "n/a" if value is None else f"{100 * float(value):.1f}%"


def render(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    return "\n".join(
        [
            "# Missing-test-surface path audit",
            "",
            f"Status: `{result['status']}`.",
            "",
            f"- Candidates: **{metrics['repositories']}**.",
            "- Complete recursive trees: "
            f"**{_pct(metrics['complete_observation_rate'])}**.",
            "- Contradicted by test paths/config: "
            f"**{metrics['contradicted_by_paths']}** "
            f"({_pct(metrics['contradiction_rate'])}).",
            "- No test path/config found: "
            f"**{metrics['supported_missing_surface']}** "
            f"({_pct(metrics['supported_missing_surface_rate'])}).",
            f"- Inconclusive: **{metrics['inconclusive']}**.",
            "",
            "A path proves test material exists, not that it is runnable or relevant",
            "to the selected project root. No path does not prove absence of "
            "behavioral",
            "validation. This audit measures false-warning risk, not business value.",
            "",
            f"Manifest: `{result['manifest_digest']}`.",
            f"Corpus: `{result['corpus_digest']}`.",
            "",
        ]
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    result = collect(args.manifest, args.corpus, args.out, args.report)
    print(result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
