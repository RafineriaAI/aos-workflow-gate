"""Deterministic pre-publication value and usability gate.

This maintainer tool evaluates evidence about *incremental* product value.
It never participates in a merge-readiness verdict and deliberately uses
``GO``/``CONDITIONAL_GO``/``NO_GO`` instead of ``PASS``/``WARN``/``BLOCK``.

The gate can reduce a discovery capture to a public-metadata-only corpus,
then assess that corpus against predeclared thresholds. Retrospective check
conclusions are never promoted to an exact historical GitHub baseline, and
an operator opinion is never promoted to an independent usefulness label.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Any

CORPUS_SCHEMA = "value-corpus-v0"
ASSESSMENT_SCHEMA = "value-assessment-v0"

THRESHOLDS: dict[str, int | float] = {
    "sample_cases": 100,
    "repositories": 10,
    "collection_complete_ratio": 0.95,
    "recurring_signal_cases": 3,
    "recurring_signal_repositories": 3,
    "exact_incremental_findings": 3,
    "exact_incremental_repositories": 3,
    "precision_labeled_cases": 20,
    "precision": 0.95,
    "qualified_external_users": 5,
    "minimum_user_runs": 3,
    "minimum_retention_days": 7,
    "next_action_rate": 1.0,
    "retention_rate": 1.0,
    "median_comprehension_seconds": 30,
}

_INDEPENDENT_LABEL_SOURCES = frozenset({"external_user", "independent_review_history"})
_LABELED_OUTCOMES = frozenset({"actionable_gap", "noise"})
_TOP_LEVEL_FIELDS = frozenset(
    {
        "boundary",
        "captured_at",
        "cases",
        "method",
        "repositories",
        "schema_version",
        "ux_observations",
    }
)
_CASE_FIELDS = frozenset(
    {
        "author_kind",
        "check_conclusions",
        "collection_complete",
        "github_baseline",
        "head_sha",
        "independent_workflow_runs",
        "outcome",
        "pull_request",
        "repository",
        "review_comments",
        "self_validating_workflows",
        "split",
        "workflow_changed",
    }
)


def _reject_nonfinite_json(token: str) -> Any:
    raise ValueError(f"non-finite JSON number is forbidden: {token}")


def _validate_corpus(corpus: dict[str, Any]) -> None:
    unknown = set(corpus) - _TOP_LEVEL_FIELDS
    if unknown:
        raise ValueError(f"value corpus has unknown fields: {sorted(unknown)}")
    for field in ("boundary", "captured_at"):
        if not isinstance(corpus.get(field), str) or not corpus[field]:
            raise ValueError(f"value corpus {field} must be a non-empty string")
    if not isinstance(corpus.get("method"), dict):
        raise ValueError("value corpus method must be an object")

    raw_cases = corpus.get("cases")
    raw_repositories = corpus.get("repositories")
    raw_ux = corpus.get("ux_observations")
    if not isinstance(raw_cases, list):
        raise ValueError("value corpus cases must be a list")
    if not isinstance(raw_repositories, list) or any(
        not isinstance(repo, str) or not repo for repo in raw_repositories
    ):
        raise ValueError("value corpus repositories must be non-empty strings")
    if not isinstance(raw_ux, list):
        raise ValueError("value corpus ux_observations must be a list")

    identities: set[tuple[str, int]] = set()
    observed_repositories: set[str] = set()
    for index, raw_case in enumerate(raw_cases):
        path = f"cases[{index}]"
        if not isinstance(raw_case, dict):
            raise ValueError(f"{path} must be an object")
        if set(raw_case) != _CASE_FIELDS:
            raise ValueError(f"{path} fields do not match {CORPUS_SCHEMA}")

        repository = raw_case["repository"]
        pull_request = raw_case["pull_request"]
        if not isinstance(repository, str) or not repository:
            raise ValueError(f"{path}.repository must be a non-empty string")
        _require_nonnegative_int(pull_request, f"{path}.pull_request", positive=True)
        identity = (repository, pull_request)
        if identity in identities:
            raise ValueError(f"{path} duplicates {repository}#{pull_request}")
        identities.add(identity)
        observed_repositories.add(repository)

        head_sha = raw_case["head_sha"]
        if (
            not isinstance(head_sha, str)
            or len(head_sha) != 40
            or any(char not in "0123456789abcdefABCDEF" for char in head_sha)
        ):
            raise ValueError(f"{path}.head_sha must be a 40-character hex SHA")
        if raw_case["author_kind"] not in {"human", "bot"}:
            raise ValueError(f"{path}.author_kind is invalid")
        if raw_case["split"] not in {"discovery", "holdout"}:
            raise ValueError(f"{path}.split is invalid")
        for field in ("collection_complete", "workflow_changed"):
            if not isinstance(raw_case[field], bool):
                raise ValueError(f"{path}.{field} must be boolean")
        for field in (
            "independent_workflow_runs",
            "self_validating_workflows",
        ):
            _require_nonnegative_int(raw_case[field], f"{path}.{field}")

        conclusions = raw_case["check_conclusions"]
        if not isinstance(conclusions, dict) or any(
            not isinstance(name, str) or not name for name in conclusions
        ):
            raise ValueError(f"{path}.check_conclusions is invalid")
        for name, count in conclusions.items():
            _require_nonnegative_int(count, f"{path}.check_conclusions[{name!r}]")

        _validate_baseline(raw_case["github_baseline"], path)
        _validate_outcome(raw_case["outcome"], path)
        comments = raw_case["review_comments"]
        if not isinstance(comments, dict) or set(comments) != {
            "ci_related",
            "total",
        }:
            raise ValueError(f"{path}.review_comments is invalid")
        for field in ("ci_related", "total"):
            _require_nonnegative_int(comments[field], f"{path}.{field}")
        if comments["ci_related"] > comments["total"]:
            raise ValueError(f"{path}.ci_related cannot exceed total")

    if raw_repositories != sorted(observed_repositories):
        raise ValueError("repositories must equal the sorted case repository set")
    for index, item in enumerate(raw_ux):
        _validate_ux_observation(item, index)


def _validate_baseline(value: Any, path: str) -> None:
    if not isinstance(value, dict) or set(value) != {
        "exact_sha",
        "merge_ready",
        "source",
    }:
        raise ValueError(f"{path}.github_baseline is invalid")
    if not isinstance(value["exact_sha"], bool):
        raise ValueError(f"{path}.github_baseline.exact_sha must be boolean")
    if value["merge_ready"] is not None and not isinstance(value["merge_ready"], bool):
        raise ValueError(f"{path}.github_baseline.merge_ready is invalid")
    if value["source"] not in {
        "github_api_snapshot",
        "unverified_historical",
    }:
        raise ValueError(f"{path}.github_baseline.source is invalid")


def _validate_outcome(value: Any, path: str) -> None:
    if not isinstance(value, dict) or set(value) != {
        "classification",
        "evidence_url",
        "source",
    }:
        raise ValueError(f"{path}.outcome is invalid")
    if value["classification"] not in {"unresolved", *_LABELED_OUTCOMES}:
        raise ValueError(f"{path}.outcome.classification is invalid")
    if value["source"] not in {"none", "operator", *_INDEPENDENT_LABEL_SOURCES}:
        raise ValueError(f"{path}.outcome.source is invalid")
    evidence_url = value["evidence_url"]
    if evidence_url is not None and (
        not isinstance(evidence_url, str) or not evidence_url.startswith("https://")
    ):
        raise ValueError(f"{path}.outcome.evidence_url is invalid")
    if value["classification"] in _LABELED_OUTCOMES and evidence_url is None:
        raise ValueError(f"{path}.outcome requires an evidence URL")


def _validate_ux_observation(value: Any, index: int) -> None:
    path = f"ux_observations[{index}]"
    required = {
        "external",
        "completed_runs",
        "retained_days",
        "kept_enabled",
        "next_action_clear",
        "understood_seconds",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError(f"{path} fields do not match {CORPUS_SCHEMA}")
    for field in ("external", "kept_enabled", "next_action_clear"):
        if not isinstance(value[field], bool):
            raise ValueError(f"{path}.{field} must be boolean")
    for field in ("completed_runs", "retained_days"):
        _require_nonnegative_int(value[field], f"{path}.{field}")

    seconds = value["understood_seconds"]
    if (
        not isinstance(seconds, (int, float))
        or isinstance(seconds, bool)
        or not math.isfinite(seconds)
        or seconds < 0
    ):
        raise ValueError(f"{path}.understood_seconds is invalid")


def _require_nonnegative_int(value: Any, path: str, *, positive: bool = False) -> None:
    minimum = 1 if positive else 0
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        qualifier = "positive" if positive else "non-negative"
        raise ValueError(f"{path} must be a {qualifier} integer")


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        parse_constant=_reject_nonfinite_json,
    )
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_corpus(manifest: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    """Reduce a discovery capture without inventing unavailable truth."""
    manifest_pulls = manifest.get("pulls")
    analysis_pulls = analysis.get("pulls")
    if not isinstance(manifest_pulls, list) or not isinstance(analysis_pulls, list):
        raise ValueError("discovery manifest and analysis need pull lists")

    membership = {
        (pull.get("repo"), pull.get("number"))
        for pull in manifest_pulls
        if isinstance(pull, dict)
    }
    analyzed = {
        (pull.get("repo"), pull.get("number"))
        for pull in analysis_pulls
        if isinstance(pull, dict)
    }
    if membership != analyzed:
        raise ValueError("discovery manifest and analysis membership differ")

    cases: list[dict[str, Any]] = []
    for pull in analysis_pulls:
        if not isinstance(pull, dict):
            raise ValueError("analysis pull entries must be objects")
        files = _mapping(pull.get("files"))
        checks = _mapping(pull.get("checks"))
        workflows = _mapping(pull.get("workflow_runs"))
        comments = _mapping(pull.get("review_comments"))
        complete = all(
            stream.get("retrievable") is True
            for stream in (files, checks, workflows, comments)
        )
        conclusions = {
            str(name): int(value)
            for name, value in _mapping(checks.get("conclusions")).items()
            if isinstance(value, int) and value >= 0
        }
        cases.append(
            {
                "author_kind": (
                    "bot"
                    if _mapping(pull.get("author")).get("bot") is True
                    else "human"
                ),
                "check_conclusions": dict(sorted(conclusions.items())),
                "collection_complete": complete,
                "github_baseline": {
                    "exact_sha": False,
                    "merge_ready": None,
                    "source": "unverified_historical",
                },
                "head_sha": str(pull.get("head_sha") or ""),
                "independent_workflow_runs": _nonnegative_int(
                    workflows.get("independent")
                ),
                "outcome": {
                    "classification": "unresolved",
                    "evidence_url": None,
                    "source": "none",
                },
                "pull_request": int(pull["number"]),
                "repository": str(pull["repo"]),
                "review_comments": {
                    "ci_related": _nonnegative_int(comments.get("ci_related")),
                    "total": _nonnegative_int(comments.get("total")),
                },
                "self_validating_workflows": _nonnegative_int(
                    workflows.get("self_validating")
                ),
                "split": str(pull.get("split") or "unknown"),
                "workflow_changed": bool(files.get("workflow")),
            }
        )

    repositories = sorted({case["repository"] for case in cases})
    return {
        "boundary": (
            "public metadata only; no code, diffs, logs, annotations, "
            "comment bodies, or commit messages are stored or executed; "
            "retrospective check conclusions are not an exact historical "
            "GitHub merge-readiness baseline"
        ),
        "captured_at": manifest.get("captured_at"),
        "cases": sorted(
            cases,
            key=lambda case: (case["repository"], case["pull_request"]),
        ),
        "method": {
            "discovery_analysis_schema": analysis.get("schema_version"),
            "discovery_manifest_schema": manifest.get("schema_version"),
            "selection": _mapping(manifest.get("method")).get("selection"),
        },
        "repositories": repositories,
        "schema_version": CORPUS_SCHEMA,
        "ux_observations": [],
    }


def assess(corpus: dict[str, Any]) -> dict[str, Any]:
    if corpus.get("schema_version") != CORPUS_SCHEMA:
        raise ValueError(f"expected {CORPUS_SCHEMA}")
    _validate_corpus(corpus)
    raw_cases = corpus.get("cases")
    raw_ux = corpus.get("ux_observations")
    if not isinstance(raw_cases, list) or not isinstance(raw_ux, list):
        raise ValueError("value corpus needs cases and ux_observations lists")
    cases = [_mapping(case) for case in raw_cases]
    ux = [_mapping(item) for item in raw_ux]

    repositories = {str(case.get("repository")) for case in cases}
    complete = [case for case in cases if case.get("collection_complete") is True]
    signals = [case for case in cases if _signal(case)]
    signal_repositories = {str(case.get("repository")) for case in signals}
    bot_signals = [case for case in signals if case.get("author_kind") == "bot"]

    exact_labeled = [case for case in signals if _exact_labeled(case)]
    actionable = [
        case
        for case in exact_labeled
        if _mapping(case.get("outcome")).get("classification") == "actionable_gap"
    ]
    noise = [
        case
        for case in exact_labeled
        if _mapping(case.get("outcome")).get("classification") == "noise"
    ]
    precision = len(actionable) / len(exact_labeled) if exact_labeled else None

    external = [item for item in ux if item.get("external") is True]
    qualified_external = [
        item
        for item in external
        if item["completed_runs"] >= THRESHOLDS["minimum_user_runs"]
        and item["retained_days"] >= THRESHOLDS["minimum_retention_days"]
    ]
    next_action_rate = _boolean_rate(qualified_external, "next_action_clear")
    retention_rate = _boolean_rate(qualified_external, "kept_enabled")
    comprehension = [
        float(item["understood_seconds"])
        for item in qualified_external
        if isinstance(item.get("understood_seconds"), (int, float))
        and not isinstance(item.get("understood_seconds"), bool)
        and float(item["understood_seconds"]) >= 0
    ]
    median_comprehension = statistics.median(comprehension) if comprehension else None

    complete_ratio = len(complete) / len(cases) if cases else 0.0
    actionable_repositories = {str(case.get("repository")) for case in actionable}
    metrics: dict[str, Any] = {
        "actionable_exact_findings": len(actionable),
        "actionable_exact_repositories": len(actionable_repositories),
        "bot_signal_cases": len(bot_signals),
        "ci_related_review_comments": sum(
            _nonnegative_int(_mapping(case.get("review_comments")).get("ci_related"))
            for case in cases
        ),
        "ci_related_review_prs": sum(
            1
            for case in cases
            if _nonnegative_int(_mapping(case.get("review_comments")).get("ci_related"))
            > 0
        ),
        "collection_complete_cases": len(complete),
        "collection_complete_ratio": complete_ratio,
        "external_users": len(external),
        "qualified_external_users": len(qualified_external),
        "labeled_signal_cases": len(exact_labeled),
        "median_comprehension_seconds": median_comprehension,
        "next_action_rate": next_action_rate,
        "noise_cases": len(noise),
        "precision": precision,
        "repositories": len(repositories),
        "retention_rate": retention_rate,
        "sample_cases": len(cases),
        "self_validating_cases": len(signals),
        "self_validating_repositories": len(signal_repositories),
    }

    technical = [
        _criterion("sample_scale", len(cases), ">=", THRESHOLDS["sample_cases"]),
        _criterion(
            "repository_diversity",
            len(repositories),
            ">=",
            THRESHOLDS["repositories"],
        ),
        _criterion(
            "collection_completeness",
            complete_ratio,
            ">=",
            THRESHOLDS["collection_complete_ratio"],
        ),
        _compound_minimum(
            "recurring_signal",
            {
                "cases": len(signals),
                "repositories": len(signal_repositories),
            },
            {
                "cases": THRESHOLDS["recurring_signal_cases"],
                "repositories": THRESHOLDS["recurring_signal_repositories"],
            },
        ),
        _compound_minimum(
            "exact_incremental_findings",
            {
                "cases": len(actionable),
                "repositories": len(actionable_repositories),
            },
            {
                "cases": THRESHOLDS["exact_incremental_findings"],
                "repositories": THRESHOLDS["exact_incremental_repositories"],
            },
        ),
        _criterion(
            "precision_sample",
            len(exact_labeled),
            ">=",
            THRESHOLDS["precision_labeled_cases"],
        ),
        _criterion(
            "observed_precision",
            precision,
            ">=",
            THRESHOLDS["precision"],
        ),
    ]
    usability = [
        _criterion(
            "qualified_external_users",
            len(qualified_external),
            ">=",
            THRESHOLDS["qualified_external_users"],
        ),
        _criterion(
            "next_action_clarity",
            next_action_rate,
            ">=",
            THRESHOLDS["next_action_rate"],
        ),
        _criterion(
            "retention",
            retention_rate,
            ">=",
            THRESHOLDS["retention_rate"],
        ),
        _criterion(
            "comprehension_time",
            median_comprehension,
            "<=",
            THRESHOLDS["median_comprehension_seconds"],
        ),
    ]
    technical_ready = all(item["met"] for item in technical)
    usability_ready = all(item["met"] for item in usability)
    status = (
        "GO"
        if technical_ready and usability_ready
        else "CONDITIONAL_GO"
        if technical_ready
        else "NO_GO"
    )
    blockers = [item["id"] for item in technical + usability if not item["met"]]
    return {
        "blockers": blockers,
        "boundary": (
            "This is a product-publication decision, not a merge-readiness "
            "verdict. Frequency is not precision; historical check states "
            "are not an exact GitHub baseline; operator labels are not "
            "independent user evidence."
        ),
        "criteria": {
            "technical_value": technical,
            "user_satisfaction": usability,
        },
        "metrics": metrics,
        "schema_version": ASSESSMENT_SCHEMA,
        "status": status,
    }


def render_markdown(assessment: dict[str, Any]) -> str:
    metrics = _mapping(assessment.get("metrics"))
    lines = [
        "# Incremental Value Gate",
        "",
        f"**Publication status: `{assessment['status']}`**",
        "",
        str(assessment["boundary"]),
        "",
        "## Measured sample",
        "",
        f"- Cases: **{metrics['sample_cases']}** across "
        f"**{metrics['repositories']}** repositories.",
        f"- Complete metadata streams: "
        f"**{metrics['collection_complete_cases']}** "
        f"({metrics['collection_complete_ratio']:.0%}).",
        f"- Self-validating workflow signal: "
        f"**{metrics['self_validating_cases']}** cases across "
        f"**{metrics['self_validating_repositories']}** repositories; "
        f"**{metrics['bot_signal_cases']}** bot-authored.",
        f"- Keyword-matched CI/test inline review comments: "
        f"**{metrics['ci_related_review_comments']}** across "
        f"**{metrics['ci_related_review_prs']}** PRs.",
        f"- Exact-baseline actionable findings: "
        f"**{metrics['actionable_exact_findings']}**; independently "
        f"labeled signal cases: **{metrics['labeled_signal_cases']}**.",
        "",
        "## Acceptance criteria",
        "",
        "| Criterion | Observed | Required | Result |",
        "| --- | --- | --- | --- |",
    ]
    criteria = _mapping(assessment.get("criteria"))
    for group in ("technical_value", "user_satisfaction"):
        for item in criteria.get(group, []):
            lines.append(
                f"| `{item['id']}` | `{_display(item['observed'])}` | "
                f"`{item['operator']} {_display(item['required'])}` | "
                f"**{'met' if item['met'] else 'not met'}** |"
            )
    lines.extend(
        [
            "",
            "## Decision rule",
            "",
            "- `GO`: technical-value and external-usability criteria pass.",
            "- `CONDITIONAL_GO`: technical value passes; only controlled "
            "external usability validation may start.",
            "- `NO_GO`: do not publish, market, or start an external pilot.",
            "",
            "Current blockers: "
            + ", ".join(f"`{item}`" for item in assessment["blockers"])
            + ".",
            "",
        ]
    )
    return "\n".join(lines)


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def _signal(case: dict[str, Any]) -> bool:
    return _nonnegative_int(case.get("self_validating_workflows")) > 0


def _exact_labeled(case: dict[str, Any]) -> bool:
    baseline = _mapping(case.get("github_baseline"))
    outcome = _mapping(case.get("outcome"))
    return bool(
        baseline.get("source") == "github_api_snapshot"
        and baseline.get("exact_sha") is True
        and baseline.get("merge_ready") is True
        and outcome.get("source") in _INDEPENDENT_LABEL_SOURCES
        and outcome.get("classification") in _LABELED_OUTCOMES
    )


def _boolean_rate(items: list[dict[str, Any]], field: str) -> float | None:
    if not items or any(not isinstance(item.get(field), bool) for item in items):
        return None
    return sum(item[field] is True for item in items) / len(items)


def _criterion(
    criterion_id: str,
    observed: Any,
    operator: str,
    required: int | float,
) -> dict[str, Any]:
    met = False
    if isinstance(observed, (int, float)) and not isinstance(observed, bool):
        met = observed >= required if operator == ">=" else observed <= required
    return {
        "id": criterion_id,
        "met": met,
        "observed": observed,
        "operator": operator,
        "required": required,
    }


def _compound_minimum(
    criterion_id: str,
    observed: dict[str, int],
    required: dict[str, int | float],
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "met": all(observed[key] >= required[key] for key in required),
        "observed": observed,
        "operator": ">= each",
        "required": required,
    }


def _display(value: Any) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, float):
        return f"{value:.3f}"
    if isinstance(value, dict):
        return ", ".join(f"{key}={value[key]}" for key in sorted(value))
    return str(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus")
    parser.add_argument("--discovery-manifest")
    parser.add_argument("--discovery-analysis")
    parser.add_argument("--corpus-out")
    parser.add_argument("--json-out")
    parser.add_argument("--markdown-out")
    parser.add_argument("--require-go", action="store_true")
    args = parser.parse_args(argv)

    corpus: dict[str, Any]
    build_args = (
        args.discovery_manifest,
        args.discovery_analysis,
        args.corpus_out,
    )
    if any(build_args):
        if not all(build_args):
            parser.error(
                "--discovery-manifest, --discovery-analysis, and "
                "--corpus-out must be provided together"
            )
        corpus = build_corpus(
            _load(Path(args.discovery_manifest)),
            _load(Path(args.discovery_analysis)),
        )
        _validate_corpus(corpus)
        _write(Path(args.corpus_out), corpus)
    elif args.corpus:
        corpus = _load(Path(args.corpus))
    else:
        parser.error("provide --corpus or the three discovery build arguments")

    assessment = assess(corpus)
    if args.json_out:
        _write(Path(args.json_out), assessment)
    markdown = render_markdown(assessment)
    if args.markdown_out:
        path = Path(args.markdown_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8", newline="\n")
    else:
        print(markdown, end="")
    return 1 if args.require_go and assessment["status"] != "GO" else 0


if __name__ == "__main__":
    raise SystemExit(main())
