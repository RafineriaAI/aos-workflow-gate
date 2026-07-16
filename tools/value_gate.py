"""Deterministic pre-publication signal and product-evidence gate.

This maintainer tool evaluates evidence about *incremental* product value.
It never participates in a merge-readiness verdict. Signal validity,
internal product readiness, practical-utility testability, external-test
readiness, external usability, and field utility are reported independently
so one kind of evidence cannot stand in for another.

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

from aos_workflow_gate import canonical

CORPUS_SCHEMA = "value-corpus-v0"
CONTRAST_SCHEMA = "value-contrast-v0"
PRODUCT_READINESS_SCHEMA = "product-test-readiness-v0"
UTILITY_READINESS_SCHEMA = "utility-test-readiness-v0"
UTILITY_TASK_CORPUS_SCHEMA = "utility-task-corpus-v0"
ASSESSMENT_SCHEMA = "value-assessment-v3"

THRESHOLDS: dict[str, int | float] = {
    "sample_cases": 100,
    "repositories": 10,
    "collection_complete_ratio": 0.95,
    "exact_semantic_contrast_cases": 3,
    "exact_semantic_contrast_repositories": 3,
    "recurring_signal_cases": 3,
    "recurring_signal_repositories": 3,
    "exact_incremental_findings": 3,
    "exact_incremental_repositories": 3,
    "precision_labeled_cases": 20,
    "precision": 0.95,
    "qualified_external_users": 8,
    "minimum_user_runs": 3,
    "minimum_retention_days": 7,
    "next_action_rate": 1.0,
    "retention_rate": 1.0,
    "median_comprehension_seconds": 30,
}

_REQUIRED_PRODUCT_CHECKS = frozenset(
    {
        "adversarial_ux",
        "clean_room_install",
        "deterministic_diagnosis",
        "external_protocol_frozen",
        "first_run_path",
        "verdict_task_corpus",
    }
)
_PRODUCT_READINESS_FIELDS = frozenset(
    {"boundary", "captured_at", "checks", "external_access", "schema_version"}
)
_PRODUCT_CHECK_FIELDS = frozenset({"evidence", "id", "status"})
_EXTERNAL_ACCESS_FIELDS = frozenset({"participants_available", "teams_available"})
_REQUIRED_UTILITY_CHECKS = frozenset(
    {
        "advisory_effect",
        "claim_firewall",
        "contrast_task",
        "deterministic_replay",
        "low_noise_controls",
        "single_next_action",
        "verdict_coverage",
    }
)
_UTILITY_READINESS_FIELDS = frozenset(
    {"boundary", "captured_at", "checks", "schema_version", "task_corpus"}
)
_UTILITY_CORPUS_FIELDS = frozenset(
    {"case_count", "digest", "negative_controls", "path", "positive_controls"}
)
_UTILITY_TASK_TOP_FIELDS = frozenset({"boundary", "cases", "schema_version"})
_UTILITY_TASK_CASE_FIELDS = frozenset(
    {"case_id", "classification", "expected", "source"}
)
_UTILITY_TASK_EXPECTED_FIELDS = frozenset(
    {"effect", "intact", "next_code", "primary_reason", "verdict"}
)
_UTILITY_TASK_SOURCE_FIELDS = {
    "adversarial_case": frozenset({"kind", "path"}),
    "bundle_policy": frozenset({"bundle", "kind", "policy"}),
    "decision_record": frozenset({"kind", "path"}),
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
_CONTRAST_METHOD_FIELDS = frozenset(
    {
        "exact_clean_non_draft_cases",
        "green_self_validating_candidates",
        "open_at_second_observation",
        "order",
        "query",
        "selection",
        "selection_trace",
        "sort",
        "state",
        "topn",
        "workflow_change_candidates",
    }
)
_CONTRAST_TOP_LEVEL_FIELDS = frozenset(
    {"boundary", "captured_at", "cases", "method", "schema_version"}
)
_CONTRAST_CASE_FIELDS = frozenset(
    {
        "aos",
        "captured_at",
        "evidence_urls",
        "github",
        "head_sha",
        "outcome",
        "pull_request",
        "repository",
        "required_non_independent_sources",
    }
)
_CONTRAST_GITHUB_FIELDS = frozenset(
    {
        "all_observed_checks_success",
        "draft",
        "exact_sha",
        "merge_state",
        "required_checks",
        "source",
        "state",
    }
)
_CONTRAST_AOS_FIELDS = frozenset(
    {
        "artifact_bundle",
        "artifact_policy",
        "artifact_record",
        "bundle_digest",
        "execution",
        "non_independent_sources",
        "reason_code",
        "record_digest",
        "self_validating_workflows",
        "verdict",
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


def _validate_contrasts(contrasts: dict[str, Any]) -> None:
    if contrasts.get("schema_version") != CONTRAST_SCHEMA:
        raise ValueError(f"expected {CONTRAST_SCHEMA}")
    if set(contrasts) != _CONTRAST_TOP_LEVEL_FIELDS:
        raise ValueError(f"contrast corpus fields do not match {CONTRAST_SCHEMA}")
    for field in ("boundary", "captured_at"):
        if not isinstance(contrasts[field], str) or not contrasts[field]:
            raise ValueError(f"contrast corpus {field} must be a non-empty string")
    if not isinstance(contrasts["method"], dict):
        raise ValueError("contrast corpus method must be an object")
    cases = contrasts["cases"]
    if not isinstance(cases, list):
        raise ValueError("contrast corpus cases must be a list")

    _validate_contrast_method(contrasts["method"], len(cases))

    identities: set[tuple[str, int]] = set()
    for index, case in enumerate(cases):
        path = f"contrast.cases[{index}]"
        if not isinstance(case, dict) or set(case) != _CONTRAST_CASE_FIELDS:
            raise ValueError(f"{path} fields do not match {CONTRAST_SCHEMA}")
        repository = case["repository"]
        pull_request = case["pull_request"]
        if not isinstance(repository, str) or not repository:
            raise ValueError(f"{path}.repository must be a non-empty string")
        _require_nonnegative_int(pull_request, f"{path}.pull_request", positive=True)
        identity = (repository, pull_request)
        if identity in identities:
            raise ValueError(f"{path} duplicates {repository}#{pull_request}")
        identities.add(identity)
        _validate_sha(case["head_sha"], f"{path}.head_sha")
        if not isinstance(case["captured_at"], str) or not case["captured_at"]:
            raise ValueError(f"{path}.captured_at must be a non-empty string")
        _validate_https_list(case["evidence_urls"], f"{path}.evidence_urls")
        _validate_contrast_github(case["github"], path)
        _validate_contrast_aos(case["aos"], path)
        _validate_outcome(case["outcome"], path)

        overlap = case["required_non_independent_sources"]
        _validate_string_list(overlap, f"{path}.required_non_independent_sources")
        required = {item["context"] for item in case["github"]["required_checks"]}
        affected = set(case["aos"]["non_independent_sources"])
        if not set(overlap) <= required & affected:
            raise ValueError(
                f"{path}.required_non_independent_sources is not a true overlap"
            )


def _validate_contrast_method(value: Any, case_count: int) -> None:
    if not isinstance(value, dict) or set(value) != _CONTRAST_METHOD_FIELDS:
        raise ValueError("contrast corpus method fields are invalid")
    for field in ("query", "selection"):
        if not isinstance(value[field], str) or not value[field]:
            raise ValueError(f"contrast corpus method {field} must be non-empty")
    expected = {
        "order": "desc",
        "selection_trace": "counts_only_not_replayable",
        "sort": "updated",
        "state": "open",
    }
    for field, expected_value in expected.items():
        if value[field] != expected_value:
            raise ValueError(f"contrast corpus method {field} is invalid")

    count_fields = (
        "topn",
        "workflow_change_candidates",
        "open_at_second_observation",
        "green_self_validating_candidates",
        "exact_clean_non_draft_cases",
    )
    for field in count_fields:
        _require_nonnegative_int(value[field], f"contrast.method.{field}")
    funnel = [value[field] for field in count_fields]
    if funnel != sorted(funnel, reverse=True) or funnel[-1] != case_count:
        raise ValueError("contrast corpus method funnel is inconsistent")


def _validate_contrast_github(value: Any, path: str) -> None:
    if not isinstance(value, dict) or set(value) != _CONTRAST_GITHUB_FIELDS:
        raise ValueError(f"{path}.github is invalid")
    for field in ("all_observed_checks_success", "draft", "exact_sha"):
        if not isinstance(value[field], bool):
            raise ValueError(f"{path}.github.{field} must be boolean")
    if value["source"] != "github_rest_snapshot":
        raise ValueError(f"{path}.github.source is invalid")
    if value["state"] not in {"open", "closed"}:
        raise ValueError(f"{path}.github.state is invalid")
    if value["merge_state"] not in {
        "behind",
        "blocked",
        "clean",
        "dirty",
        "draft",
        "has_hooks",
        "unknown",
        "unstable",
    }:
        raise ValueError(f"{path}.github.merge_state is invalid")
    required = value["required_checks"]
    if not isinstance(required, list):
        raise ValueError(f"{path}.github.required_checks must be a list")
    identities: set[tuple[str, int | None]] = set()
    for index, item in enumerate(required):
        item_path = f"{path}.github.required_checks[{index}]"
        if not isinstance(item, dict) or set(item) != {"context", "integration_id"}:
            raise ValueError(f"{item_path} is invalid")
        context = item["context"]
        integration = item["integration_id"]
        if not isinstance(context, str) or not context:
            raise ValueError(f"{item_path}.context must be a non-empty string")
        if integration is not None:
            _require_nonnegative_int(
                integration, f"{item_path}.integration_id", positive=True
            )
        identity = (context, integration)
        if identity in identities:
            raise ValueError(f"{item_path} duplicates a required check")
        identities.add(identity)


def _validate_contrast_aos(value: Any, path: str) -> None:
    if not isinstance(value, dict) or set(value) != _CONTRAST_AOS_FIELDS:
        raise ValueError(f"{path}.aos is invalid")
    if value["execution"] not in {"live_full_cli", "live_api_engine_replay"}:
        raise ValueError(f"{path}.aos.execution is invalid")
    if value["verdict"] not in {"PASS", "WARN", "BLOCK"}:
        raise ValueError(f"{path}.aos.verdict is invalid")
    if not isinstance(value["reason_code"], str) or not value["reason_code"]:
        raise ValueError(f"{path}.aos.reason_code must be a non-empty string")
    for field in ("non_independent_sources", "self_validating_workflows"):
        _validate_string_list(value[field], f"{path}.aos.{field}", nonempty=True)

    artifacts = (
        value["artifact_bundle"],
        value["artifact_policy"],
        value["artifact_record"],
    )
    digests = (value["bundle_digest"], value["record_digest"])
    if value["execution"] == "live_full_cli":
        for artifact in artifacts:
            if (
                not isinstance(artifact, str)
                or not artifact
                or "\\" in artifact
                or ".." in Path(artifact).parts
            ):
                raise ValueError(f"{path}.aos artifact path is invalid")
        for digest in digests:
            _validate_digest(digest, f"{path}.aos digest")
    elif any(item is not None for item in (*artifacts, *digests)):
        raise ValueError(f"{path}.aos engine replay cannot claim canonical artifacts")


def _validate_sha(value: Any, path: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 40
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise ValueError(f"{path} must be a lowercase 40-character hex SHA")


def _validate_digest(value: Any, path: str) -> None:
    if (
        not isinstance(value, str)
        or not value.startswith("sha256:")
        or len(value) != 71
        or any(char not in "0123456789abcdef" for char in value[7:])
    ):
        raise ValueError(f"{path} must be a canonical sha256 digest")


def _validate_string_list(value: Any, path: str, *, nonempty: bool = False) -> None:
    if (
        not isinstance(value, list)
        or (nonempty and not value)
        or any(not isinstance(item, str) or not item for item in value)
        or len(value) != len(set(value))
        or value != sorted(value)
    ):
        raise ValueError(f"{path} must be a sorted unique string list")


def _validate_https_list(value: Any, path: str) -> None:
    if (
        not isinstance(value, list)
        or not value
        or any(
            not isinstance(item, str) or not item.startswith("https://")
            for item in value
        )
        or len(value) != len(set(value))
    ):
        raise ValueError(f"{path} must be a unique non-empty HTTPS URL list")


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


def _validate_product_readiness(value: dict[str, Any]) -> None:
    if value.get("schema_version") != PRODUCT_READINESS_SCHEMA:
        raise ValueError(f"expected {PRODUCT_READINESS_SCHEMA}")
    if set(value) != _PRODUCT_READINESS_FIELDS:
        raise ValueError(
            f"product readiness fields do not match {PRODUCT_READINESS_SCHEMA}"
        )
    for field in ("boundary", "captured_at"):
        if not isinstance(value[field], str) or not value[field]:
            raise ValueError(f"product readiness {field} must be non-empty")

    access = value["external_access"]
    if not isinstance(access, dict) or set(access) != _EXTERNAL_ACCESS_FIELDS:
        raise ValueError("product readiness external_access is invalid")
    if any(not isinstance(access[field], bool) for field in access):
        raise ValueError("product readiness external_access values must be boolean")

    checks = value["checks"]
    if not isinstance(checks, list):
        raise ValueError("product readiness checks must be a list")
    observed_ids: set[str] = set()
    for index, check in enumerate(checks):
        path = f"product_readiness.checks[{index}]"
        if not isinstance(check, dict) or set(check) != _PRODUCT_CHECK_FIELDS:
            raise ValueError(f"{path} fields are invalid")
        check_id = check["id"]
        if not isinstance(check_id, str) or not check_id:
            raise ValueError(f"{path}.id must be non-empty")
        if check_id in observed_ids:
            raise ValueError(f"{path}.id is duplicated")
        observed_ids.add(check_id)
        if check["status"] not in {"met", "not_met"}:
            raise ValueError(f"{path}.status is invalid")
        evidence = check["evidence"]
        if (
            not isinstance(evidence, list)
            or not evidence
            or any(not isinstance(item, str) or not item for item in evidence)
            or evidence != sorted(set(evidence))
        ):
            raise ValueError(f"{path}.evidence must be a sorted unique string list")
    if observed_ids != _REQUIRED_PRODUCT_CHECKS:
        raise ValueError(
            "product readiness checks must equal the frozen required check set"
        )


def _validate_utility_readiness(value: dict[str, Any]) -> None:
    if value.get("schema_version") != UTILITY_READINESS_SCHEMA:
        raise ValueError(f"expected {UTILITY_READINESS_SCHEMA}")
    if set(value) != _UTILITY_READINESS_FIELDS:
        raise ValueError(
            f"utility readiness fields do not match {UTILITY_READINESS_SCHEMA}"
        )
    for field in ("boundary", "captured_at"):
        if not isinstance(value[field], str) or not value[field]:
            raise ValueError(f"utility readiness {field} must be non-empty")

    corpus = value["task_corpus"]
    if not isinstance(corpus, dict) or set(corpus) != _UTILITY_CORPUS_FIELDS:
        raise ValueError("utility readiness task_corpus is invalid")
    _validate_relative_artifact_path(
        corpus["path"], "utility readiness task_corpus.path"
    )
    _validate_digest(corpus["digest"], "utility readiness task_corpus.digest")
    for field in ("case_count", "negative_controls", "positive_controls"):
        _require_nonnegative_int(
            corpus[field],
            f"utility readiness task_corpus.{field}",
            positive=True,
        )
    if (
        corpus["negative_controls"] + corpus["positive_controls"]
        != corpus["case_count"]
    ):
        raise ValueError("utility readiness task_corpus counts are inconsistent")

    checks = value["checks"]
    if not isinstance(checks, list):
        raise ValueError("utility readiness checks must be a list")
    observed_ids: set[str] = set()
    for index, check in enumerate(checks):
        path = f"utility_readiness.checks[{index}]"
        if not isinstance(check, dict) or set(check) != _PRODUCT_CHECK_FIELDS:
            raise ValueError(f"{path} fields are invalid")
        check_id = check["id"]
        if not isinstance(check_id, str) or not check_id:
            raise ValueError(f"{path}.id must be non-empty")
        if check_id in observed_ids:
            raise ValueError(f"{path}.id is duplicated")
        observed_ids.add(check_id)
        if check["status"] not in {"met", "not_met"}:
            raise ValueError(f"{path}.status is invalid")
        evidence = check["evidence"]
        if (
            not isinstance(evidence, list)
            or not evidence
            or any(not isinstance(item, str) or not item for item in evidence)
            or evidence != sorted(set(evidence))
        ):
            raise ValueError(f"{path}.evidence must be a sorted unique string list")
    if observed_ids != _REQUIRED_UTILITY_CHECKS:
        raise ValueError(
            "utility readiness checks must equal the frozen required check set"
        )


def _validate_relative_artifact_path(value: Any, path: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or Path(value).is_absolute()
        or "\\" in value
        or ".." in Path(value).parts
    ):
        raise ValueError(f"{path} is invalid")
    return value


def _validate_utility_task_corpus(value: dict[str, Any]) -> None:
    if value.get("schema_version") != UTILITY_TASK_CORPUS_SCHEMA:
        raise ValueError(f"expected {UTILITY_TASK_CORPUS_SCHEMA}")
    if set(value) != _UTILITY_TASK_TOP_FIELDS:
        raise ValueError(
            f"utility task corpus fields do not match {UTILITY_TASK_CORPUS_SCHEMA}"
        )
    if not isinstance(value["boundary"], str) or not value["boundary"]:
        raise ValueError("utility task corpus boundary must be non-empty")

    cases = value["cases"]
    if not isinstance(cases, list) or not cases:
        raise ValueError("utility task corpus cases must be a non-empty list")
    case_ids: list[str] = []
    classifications: set[str] = set()
    verdicts: set[str] = set()
    for index, case in enumerate(cases):
        path = f"utility_task_corpus.cases[{index}]"
        if not isinstance(case, dict) or set(case) != _UTILITY_TASK_CASE_FIELDS:
            raise ValueError(f"{path} fields are invalid")
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not case_id:
            raise ValueError(f"{path}.case_id must be non-empty")
        case_ids.append(case_id)

        classification = case["classification"]
        if classification not in {"negative_control", "positive_control"}:
            raise ValueError(f"{path}.classification is invalid")
        classifications.add(classification)

        expected = case["expected"]
        if (
            not isinstance(expected, dict)
            or set(expected) != _UTILITY_TASK_EXPECTED_FIELDS
        ):
            raise ValueError(f"{path}.expected fields are invalid")
        verdict = expected["verdict"]
        if verdict not in {"BLOCK", "PASS", "WARN"}:
            raise ValueError(f"{path}.expected.verdict is invalid")
        verdicts.add(verdict)
        if expected["effect"] != "advisory":
            raise ValueError(f"{path}.expected.effect must be advisory")
        if not isinstance(expected["intact"], bool):
            raise ValueError(f"{path}.expected.intact must be boolean")
        if not isinstance(expected["next_code"], str) or not expected["next_code"]:
            raise ValueError(f"{path}.expected.next_code must be non-empty")
        primary_reason = expected["primary_reason"]
        if verdict == "PASS":
            if primary_reason is not None or classification != "positive_control":
                raise ValueError(f"{path} PASS must be a reason-free positive control")
        elif (
            not isinstance(primary_reason, str)
            or not primary_reason
            or classification != "negative_control"
        ):
            raise ValueError(f"{path} non-PASS must name a negative-control reason")

        source = case["source"]
        if not isinstance(source, dict):
            raise ValueError(f"{path}.source must be an object")
        kind = source.get("kind")
        expected_fields = (
            _UTILITY_TASK_SOURCE_FIELDS.get(kind) if isinstance(kind, str) else None
        )
        if expected_fields is None or set(source) != expected_fields:
            raise ValueError(f"{path}.source fields are invalid")
        for field in expected_fields - {"kind"}:
            _validate_relative_artifact_path(source[field], f"{path}.source.{field}")

    if len(case_ids) != len(set(case_ids)) or case_ids != sorted(case_ids):
        raise ValueError("utility task corpus case IDs must be sorted and unique")
    if classifications != {"negative_control", "positive_control"}:
        raise ValueError("utility task corpus must contain both control classes")
    if verdicts != {"BLOCK", "PASS", "WARN"}:
        raise ValueError("utility task corpus must cover PASS, WARN, and BLOCK")


def _validate_utility_binding(
    readiness: dict[str, Any],
    task_corpus: dict[str, Any],
) -> None:
    _validate_utility_task_corpus(task_corpus)
    binding = readiness["task_corpus"]
    if canonical.digest(task_corpus) != binding["digest"]:
        raise ValueError("utility task corpus does not match its canonical digest")
    cases = task_corpus["cases"]
    positive = sum(case["classification"] == "positive_control" for case in cases)
    negative = sum(case["classification"] == "negative_control" for case in cases)
    if (
        len(cases) != binding["case_count"]
        or positive != binding["positive_controls"]
        or negative != binding["negative_controls"]
    ):
        raise ValueError("utility task corpus does not match its bound counts")


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


def assess(
    corpus: dict[str, Any],
    *,
    product_readiness: dict[str, Any] | None = None,
    utility_readiness: dict[str, Any] | None = None,
    utility_task_corpus: dict[str, Any] | None = None,
    contrasts: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if corpus.get("schema_version") != CORPUS_SCHEMA:
        raise ValueError(f"expected {CORPUS_SCHEMA}")
    _validate_corpus(corpus)
    if utility_readiness is not None:
        _validate_utility_readiness(utility_readiness)
        if utility_task_corpus is None:
            raise ValueError("utility readiness requires its bound task corpus")
        _validate_utility_binding(utility_readiness, utility_task_corpus)
    elif utility_task_corpus is not None:
        raise ValueError("utility task corpus requires a readiness manifest")
    if product_readiness is not None:
        _validate_product_readiness(product_readiness)

    contrast_cases: list[dict[str, Any]] = []
    if contrasts is not None:
        _validate_contrasts(contrasts)
        contrast_cases = [_mapping(case) for case in contrasts["cases"]]

    raw_cases = corpus.get("cases")
    raw_ux = corpus.get("ux_observations")
    if not isinstance(raw_cases, list) or not isinstance(raw_ux, list):
        raise ValueError("value corpus needs cases and ux_observations lists")
    cases = [_mapping(case) for case in raw_cases]
    ux = [_mapping(item) for item in raw_ux]

    readiness = product_readiness or {}
    access = _mapping(readiness.get("external_access"))
    participants_available = access.get("participants_available") is True
    teams_available = access.get("teams_available") is True
    readiness_by_id = {
        str(item.get("id")): _mapping(item)
        for item in readiness.get("checks", [])
        if isinstance(item, dict)
    }
    utility = utility_readiness or {}
    utility_corpus = _mapping(utility.get("task_corpus"))
    utility_by_id = {
        str(item.get("id")): _mapping(item)
        for item in utility.get("checks", [])
        if isinstance(item, dict)
    }

    repositories = {str(case.get("repository")) for case in cases}
    complete = [case for case in cases if case.get("collection_complete") is True]
    signals = [case for case in cases if _signal(case)]
    signal_repositories = {str(case.get("repository")) for case in signals}
    bot_signals = [case for case in signals if case.get("author_kind") == "bot"]

    mechanical_contrasts = [
        case for case in contrast_cases if _exact_semantic_contrast(case)
    ]
    contrast_repositories = {
        str(case.get("repository")) for case in mechanical_contrasts
    }
    replayable_contrasts = [
        case
        for case in mechanical_contrasts
        if _mapping(case.get("aos")).get("execution") == "live_full_cli"
    ]
    required_overlap = [
        case
        for case in mechanical_contrasts
        if case.get("required_non_independent_sources")
    ]
    contrast_labeled = [
        case for case in mechanical_contrasts if _independently_labeled(case)
    ]

    exact_labeled = [
        case for case in signals if _exact_labeled(case)
    ] + contrast_labeled
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
    if external and not participants_available:
        raise ValueError(
            "external usability observations contradict unavailable participants"
        )
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
    product_checks_met = sum(
        _mapping(readiness_by_id.get(check_id)).get("status") == "met"
        for check_id in _REQUIRED_PRODUCT_CHECKS
    )
    utility_checks_met = sum(
        _mapping(utility_by_id.get(check_id)).get("status") == "met"
        for check_id in _REQUIRED_UTILITY_CHECKS
    )
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
        "contrast_sample_cases": len(contrast_cases),
        "exact_semantic_contrast_cases": len(mechanical_contrasts),
        "exact_semantic_contrast_repositories": len(contrast_repositories),
        "external_participants_available": participants_available,
        "external_teams_available": teams_available,
        "external_users": len(external),
        "independently_labeled_contrast_cases": len(contrast_labeled),
        "labeled_signal_cases": len(exact_labeled),
        "median_comprehension_seconds": median_comprehension,
        "next_action_rate": next_action_rate,
        "utility_negative_controls": _nonnegative_int(
            utility_corpus.get("negative_controls")
        ),
        "utility_positive_controls": _nonnegative_int(
            utility_corpus.get("positive_controls")
        ),
        "utility_readiness_checks_met": utility_checks_met,
        "utility_readiness_checks_required": len(_REQUIRED_UTILITY_CHECKS),
        "utility_task_cases": _nonnegative_int(utility_corpus.get("case_count")),
        "noise_cases": len(noise),
        "precision": precision,
        "product_readiness_checks_met": product_checks_met,
        "product_readiness_checks_required": len(_REQUIRED_PRODUCT_CHECKS),
        "qualified_external_users": len(qualified_external),
        "replayable_contrast_cases": len(replayable_contrasts),
        "repositories": len(repositories),
        "required_non_independent_check_cases": len(required_overlap),
        "required_non_independent_sources": sum(
            len(case["required_non_independent_sources"]) for case in required_overlap
        ),
        "retention_rate": retention_rate,
        "sample_cases": len(cases),
        "self_validating_cases": len(signals),
        "self_validating_repositories": len(signal_repositories),
    }

    mechanism_evidence = [
        _compound_minimum(
            "exact_semantic_contrast",
            {
                "cases": len(mechanical_contrasts),
                "repositories": len(contrast_repositories),
            },
            {
                "cases": THRESHOLDS["exact_semantic_contrast_cases"],
                "repositories": THRESHOLDS["exact_semantic_contrast_repositories"],
            },
        )
    ]
    signal_validity = [
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
    product_test = [
        _state_criterion(
            f"product_{check_id}",
            _mapping(readiness_by_id.get(check_id)).get("status"),
            "met",
        )
        for check_id in sorted(_REQUIRED_PRODUCT_CHECKS)
    ]
    utility_test = [
        _state_criterion(
            f"utility_{check_id}",
            _mapping(utility_by_id.get(check_id)).get("status"),
            "met",
        )
        for check_id in sorted(_REQUIRED_UTILITY_CHECKS)
    ]
    external_usability = [
        _state_criterion(
            "controlled_comparative_study",
            "not_run",
            "verified",
        ),
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

    mechanism_ready = all(item["met"] for item in mechanism_evidence)
    signal_ready = all(item["met"] for item in signal_validity)
    utility_test_ready = all(item["met"] for item in utility_test)
    product_test_ready = all(item["met"] for item in product_test)
    usability_ready = all(item["met"] for item in external_usability)

    signal_by_id = {item["id"]: item for item in signal_validity}
    signal_evidence_sufficient = all(
        signal_by_id[criterion_id]["met"]
        for criterion_id in (
            "sample_scale",
            "repository_diversity",
            "collection_completeness",
            "recurring_signal",
            "precision_sample",
        )
    )
    mechanism_status = (
        "MECHANISM_CONFIRMED" if mechanism_ready else "MECHANISM_INCOMPLETE"
    )
    signal_status = (
        "SIGNAL_SUPPORTED"
        if signal_ready
        else "SIGNAL_NOT_SUPPORTED"
        if signal_evidence_sufficient
        else "SIGNAL_INCONCLUSIVE"
    )
    product_status = (
        "PRODUCT_TEST_READY" if product_test_ready else "PRODUCT_TEST_INCOMPLETE"
    )
    external_status = (
        "EXTERNAL_VALIDATION_PENDING"
        if not external
        else "EXTERNAL_VALIDATION_INCONCLUSIVE"
    )
    field_status = (
        "FIELD_VALIDATION_NOT_STARTED"
        if teams_available
        else "FIELD_VALIDATION_PENDING"
    )
    utility_status = (
        "UTILITY_TEST_READY" if utility_test_ready else "UTILITY_TEST_INCOMPLETE"
    )
    external_test_ready = (
        mechanism_ready
        and product_test_ready
        and utility_test_ready
        and signal_status != "SIGNAL_NOT_SUPPORTED"
    )
    external_test_status = (
        "READY_FOR_EXTERNAL_VALIDATION"
        if external_test_ready
        else "NOT_READY_FOR_EXTERNAL_VALIDATION"
    )
    participant_access_status = (
        "PARTICIPANTS_AVAILABLE" if participants_available else "RECRUITMENT_PENDING"
    )
    status = (
        "GO"
        if (
            mechanism_ready
            and signal_ready
            and product_test_ready
            and utility_test_ready
            and usability_ready
        )
        else "NO_GO"
    )

    mechanism_blockers = [item["id"] for item in mechanism_evidence if not item["met"]]
    signal_blockers = [item["id"] for item in signal_validity if not item["met"]]
    product_blockers = [item["id"] for item in product_test if not item["met"]]
    utility_blockers = [item["id"] for item in utility_test if not item["met"]]
    usability_blockers = [item["id"] for item in external_usability if not item["met"]]
    external_test_blockers = (
        mechanism_blockers
        + product_blockers
        + utility_blockers
        + (["signal_not_supported"] if signal_status == "SIGNAL_NOT_SUPPORTED" else [])
    )
    return {
        "blockers": (
            mechanism_blockers
            + signal_blockers
            + product_blockers
            + utility_blockers
            + usability_blockers
        ),
        "boundary": (
            "This is a product-publication decision, not a merge-readiness "
            "verdict. Exact-SHA contrast can establish only a semantic "
            "difference from GitHub. Internal utility tasks establish only "
            "testability of the diagnosis, not practical usefulness. Signal "
            "validity, product testability, external usability, and field "
            "utility are separate claims. Internal tests and public repository "
            "history are never user evidence."
        ),
        "criteria": {
            "external_usability": external_usability,
            "mechanism_evidence": mechanism_evidence,
            "practical_utility_testability": utility_test,
            "product_test_readiness": product_test,
            "signal_validity": signal_validity,
        },
        "external_test_blockers": external_test_blockers,
        "metrics": metrics,
        "schema_version": ASSESSMENT_SCHEMA,
        "status": status,
        "tracks": {
            "external_test_readiness": external_test_status,
            "external_usability": external_status,
            "field_utility": field_status,
            "mechanism_evidence": mechanism_status,
            "participant_access": participant_access_status,
            "practical_utility_testability": utility_status,
            "product_test_readiness": product_status,
            "signal_validity": signal_status,
        },
    }


def render_markdown(assessment: dict[str, Any]) -> str:
    metrics = _mapping(assessment.get("metrics"))
    tracks = _mapping(assessment.get("tracks"))
    lines = [
        "# Hybrid Value Gate",
        "",
        f"**Publication status: `{assessment['status']}`**",
        "",
        str(assessment["boundary"]),
        "",
        "## Track status",
        "",
        f"- Mechanism evidence: `{tracks['mechanism_evidence']}`.",
        f"- Signal validity: `{tracks['signal_validity']}`.",
        f"- Internal product test: `{tracks['product_test_readiness']}`.",
        f"- Practical-utility testability: "
        f"`{tracks['practical_utility_testability']}`.",
        f"- External-test readiness: `{tracks['external_test_readiness']}`.",
        f"- Participant access: `{tracks['participant_access']}`.",
        f"- External usability: `{tracks['external_usability']}`.",
        f"- Field utility: `{tracks['field_utility']}`.",
        "",
        "## Measured signal sample",
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
        "## Exact-SHA semantic contrast",
        "",
        f"- GitHub `clean` plus AOS `WARN/non_independent_evidence`: "
        f"**{metrics['exact_semantic_contrast_cases']}** cases across "
        f"**{metrics['exact_semantic_contrast_repositories']}** repositories.",
        f"- Full canonical bundle/policy/record replay: "
        f"**{metrics['replayable_contrast_cases']}** cases.",
        f"- A required GitHub check was non-independent: "
        f"**{metrics['required_non_independent_check_cases']}** case(s), "
        f"**{metrics['required_non_independent_sources']}** source(s).",
        f"- Independently adjudicated contrast outcomes: "
        f"**{metrics['independently_labeled_contrast_cases']}**.",
        "- Interpretation: semantic difference is demonstrated; usefulness "
        "and precision remain unproven until outcomes are independently labeled.",
        "",
        "## Product-test readiness",
        "",
        f"- Internal checks: **{metrics['product_readiness_checks_met']}**/"
        f"**{metrics['product_readiness_checks_required']}** met.",
        f"- External participants currently available: "
        f"**{'yes' if metrics['external_participants_available'] else 'no'}**.",
        f"- External teams currently available: "
        f"**{'yes' if metrics['external_teams_available'] else 'no'}**.",
        f"- Qualified external users observed: "
        f"**{metrics['qualified_external_users']}**.",
        "- Internal checks can establish only PRODUCT_TEST_READY; they cannot "
        "establish product usefulness, adoption, retention, or willingness to pay.",
        "",
        "## Practical-utility testability",
        "",
        f"- Frozen internal tasks: **{metrics['utility_task_cases']}**; "
        f"positive controls: **{metrics['utility_positive_controls']}**; "
        f"negative controls: **{metrics['utility_negative_controls']}**.",
        f"- Internal checks: **{metrics['utility_readiness_checks_met']}**/"
        f"**{metrics['utility_readiness_checks_required']}** met.",
        "- These tasks verify deterministic diagnosis and one actionable Next. "
        "They do not measure whether an external developer understands, trusts, "
        "uses, retains, or pays for the product.",
        "",
        "## Acceptance criteria",
        "",
        "| Track | Criterion | Observed | Required | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    criteria = _mapping(assessment.get("criteria"))
    for group in (
        "mechanism_evidence",
        "signal_validity",
        "product_test_readiness",
        "practical_utility_testability",
        "external_usability",
    ):
        for item in criteria.get(group, []):
            lines.append(
                f"| `{group}` | `{item['id']}` | "
                f"`{_display(item['observed'])}` | "
                f"`{item['operator']} {_display(item['required'])}` | "
                f"**{'met' if item['met'] else 'not met'}** |"
            )
    lines.extend(
        [
            "",
            "## Decision rule",
            "",
            "- `MECHANISM_CONFIRMED` proves only that AOS can produce "
            "decision-relevant information absent from the observed GitHub baseline.",
            "- `READY_FOR_EXTERNAL_VALIDATION` requires confirmed mechanism, "
            "internal product readiness, and the frozen utility-task corpus. "
            "`SIGNAL_INCONCLUSIVE` may be studied; `SIGNAL_NOT_SUPPORTED` blocks it.",
            "- `READY_FOR_EXTERNAL_VALIDATION` permits only recruitment and a "
            "controlled advisory study. It is not `PRODUCT_USEFUL`, pilot readiness, "
            "or publication approval.",
            "- `GO` additionally requires `SIGNAL_SUPPORTED` and independently "
            "supported external usability.",
            "- Commercialization remains unvalidated until a separate field "
            "study establishes practical utility and retention.",
            "- `NO_GO` blocks publication, marketing, production "
            "recommendations, and paid pilot intake.",
            "",
            "Current publication blockers: "
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


def _exact_semantic_contrast(case: dict[str, Any]) -> bool:
    github = _mapping(case.get("github"))
    aos = _mapping(case.get("aos"))
    return bool(
        github.get("source") == "github_rest_snapshot"
        and github.get("exact_sha") is True
        and github.get("state") == "open"
        and github.get("draft") is False
        and github.get("merge_state") == "clean"
        and github.get("all_observed_checks_success") is True
        and aos.get("verdict") == "WARN"
        and aos.get("reason_code") == "non_independent_evidence"
        and aos.get("non_independent_sources")
        and aos.get("self_validating_workflows")
    )


def _independently_labeled(case: dict[str, Any]) -> bool:
    outcome = _mapping(case.get("outcome"))
    return bool(
        outcome.get("source") in _INDEPENDENT_LABEL_SOURCES
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


def _state_criterion(
    criterion_id: str,
    observed: Any,
    required: str,
) -> dict[str, Any]:
    return {
        "id": criterion_id,
        "met": observed == required,
        "observed": observed,
        "operator": "==",
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
    parser.add_argument("--product-readiness")
    parser.add_argument("--utility-readiness")
    parser.add_argument("--contrast-corpus")
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

    product_readiness = (
        _load(Path(args.product_readiness)) if args.product_readiness else None
    )
    utility_readiness: dict[str, Any] | None = None
    utility_task_corpus: dict[str, Any] | None = None
    if args.utility_readiness:
        utility_readiness = _load(Path(args.utility_readiness))
        _validate_utility_readiness(utility_readiness)
        task_path = _validate_relative_artifact_path(
            utility_readiness["task_corpus"]["path"],
            "utility readiness task_corpus.path",
        )
        utility_task_corpus = _load(Path(task_path))
    contrasts = _load(Path(args.contrast_corpus)) if args.contrast_corpus else None
    assessment = assess(
        corpus,
        product_readiness=product_readiness,
        utility_readiness=utility_readiness,
        utility_task_corpus=utility_task_corpus,
        contrasts=contrasts,
    )
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
