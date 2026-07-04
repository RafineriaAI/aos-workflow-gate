"""Policy model and loader.

A policy is operator-controlled configuration. Because the operator owns it,
a malformed policy is a hard error (``InputError``) rather than a fail-closed
decision: the gate must not guess what an unreadable policy meant.

Policies may be written as JSON or as a small restricted YAML subset. The
restricted reader intentionally rejects anything outside the documented shape,
which keeps configuration auditable and dependency-free.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import canonical
from .errors import InputError

REQUIRED_RULE_KEYS = (
    "missing_required_source",
    "failed_required_source",
    "malformed_input",
    "advisory_warning",
)
VALID_SEVERITIES = frozenset({"PASS", "WARN", "BLOCK"})
VALID_MODES = frozenset({"advisory", "blocking"})


@dataclass
class Policy:
    """A validated, normalized gate policy."""

    schema_version: str
    policy_id: str
    mode: str
    verification_status: str
    require_repository: bool
    require_sha: bool
    rules: dict[str, str]
    required_sources: tuple[str, ...]
    advisory_sources: tuple[str, ...]
    normalized: dict[str, Any]

    @property
    def digest(self) -> str:
        """Content digest over the normalized policy (format-independent)."""
        return canonical.digest(self.normalized)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Policy:
        policy_id = _require_str(data, "policy_id")
        schema_version = _optional_str(data, "schema_version", "")
        mode = _optional_str(data, "mode", "advisory")
        if mode not in VALID_MODES:
            raise InputError(f"policy: mode must be one of {sorted(VALID_MODES)}")
        verification_status = _optional_str(
            data, "verification_status", "UNSIGNED_NOT_OFFICIAL"
        )

        subject = data.get("subject", {})
        if not isinstance(subject, dict):
            raise InputError("policy: subject must be a mapping")
        require_repository = _optional_bool(subject, "require_repository", False)
        require_sha = _optional_bool(subject, "require_sha", False)

        rules = _parse_rules(data.get("rules"))
        required_sources = _parse_id_list(data, "required_sources")
        advisory_sources = _parse_id_list(data, "advisory_sources")

        normalized: dict[str, Any] = {
            "schema_version": schema_version,
            "policy_id": policy_id,
            "mode": mode,
            "verification_status": verification_status,
            "subject": {
                "require_repository": require_repository,
                "require_sha": require_sha,
            },
            "rules": dict(sorted(rules.items())),
            "required_sources": list(required_sources),
            "advisory_sources": list(advisory_sources),
        }
        return cls(
            schema_version=schema_version,
            policy_id=policy_id,
            mode=mode,
            verification_status=verification_status,
            require_repository=require_repository,
            require_sha=require_sha,
            rules=rules,
            required_sources=required_sources,
            advisory_sources=advisory_sources,
            normalized=normalized,
        )


def load_policy(path: Path) -> Policy:
    """Load and validate a policy from a JSON or restricted-YAML file."""
    text = path.read_text(encoding="utf-8")
    stripped = text.lstrip()
    if path.suffix == ".json" or stripped.startswith("{"):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise InputError(f"policy: invalid JSON: {exc}") from exc
    else:
        data = parse_restricted_yaml(text)
    if not isinstance(data, dict):
        raise InputError("policy: root must be a mapping")
    return Policy.from_dict(data)


def _require_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise InputError(f"policy: '{key}' must be a non-empty string")
    return value


def _optional_str(data: dict[str, Any], key: str, default: str) -> str:
    value = data.get(key, default)
    if not isinstance(value, str):
        raise InputError(f"policy: '{key}' must be a string")
    return value


def _optional_bool(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if not isinstance(value, bool):
        raise InputError(f"policy: '{key}' must be a boolean")
    return value


def _parse_rules(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise InputError("policy: 'rules' must be a mapping")
    rules: dict[str, str] = {}
    for key, value in raw.items():
        if not isinstance(value, str) or value not in VALID_SEVERITIES:
            raise InputError(
                f"policy: rule '{key}' must be one of {sorted(VALID_SEVERITIES)}"
            )
        rules[key] = value
    for required in REQUIRED_RULE_KEYS:
        if required not in rules:
            raise InputError(f"policy: 'rules' is missing '{required}'")
    return rules


def _parse_id_list(data: dict[str, Any], key: str) -> tuple[str, ...]:
    raw = data.get(key, [])
    if not isinstance(raw, list):
        raise InputError(f"policy: '{key}' must be a list")
    ids: list[str] = []
    for item in raw:
        if not isinstance(item, str) or not item:
            raise InputError(f"policy: '{key}' entries must be non-empty strings")
        ids.append(item)
    if len(ids) != len(set(ids)):
        raise InputError(f"policy: '{key}' contains duplicate ids")
    return tuple(ids)


def parse_restricted_yaml(text: str) -> dict[str, Any]:
    """Parse the restricted YAML subset used by policy files.

    Supported: top-level ``key: value`` scalars, one level of 2-space nested
    ``key: value`` mappings, and 2-space nested ``- item`` lists. Anything else
    (tabs, deeper nesting, inline structures) is rejected, which keeps policies
    unambiguous and dependency-free.
    """
    result: dict[str, Any] = {}
    lines = text.splitlines()
    index = 0
    total = len(lines)
    while index < total:
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if "\t" in line:
            raise InputError("policy: tabs are not allowed")
        if _indent_of(line) != 0:
            raise InputError(f"policy: unexpected indentation at line {index + 1}")
        key, has_colon, rest = line.strip().partition(":")
        if not has_colon:
            raise InputError(f"policy: expected 'key:' at line {index + 1}")
        key = key.strip()
        rest = rest.strip()
        if rest:
            result[key] = _parse_scalar(rest)
            index += 1
            continue
        block, index = _collect_block(lines, index + 1, total)
        result[key] = _parse_block(key, block)
    return result


def _collect_block(
    lines: list[str], start: int, total: int
) -> tuple[list[str], int]:
    block: list[str] = []
    index = start
    while index < total:
        line = lines[index]
        if not line.strip() or line.lstrip().startswith("#"):
            index += 1
            continue
        if _indent_of(line) == 0:
            break
        if "\t" in line:
            raise InputError("policy: tabs are not allowed")
        if _indent_of(line) != 2:
            raise InputError(f"policy: expected 2-space indent at line {index + 1}")
        block.append(line.strip())
        index += 1
    return block, index


def _parse_block(key: str, block: list[str]) -> Any:
    if not block:
        return {}
    if all(item == "-" or item.startswith("- ") for item in block):
        return [_parse_scalar(item[1:].strip()) for item in block]
    mapping: dict[str, Any] = {}
    for item in block:
        if item.startswith("- "):
            raise InputError(f"policy: mixed list and mapping under '{key}'")
        sub_key, has_colon, sub_value = item.partition(":")
        if not has_colon:
            raise InputError(f"policy: expected 'key: value' under '{key}'")
        mapping[sub_key.strip()] = _parse_scalar(sub_value.strip())
    return mapping


def _parse_scalar(token: str) -> Any:
    lowered = token.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in ("null", "~", ""):
        return None
    if len(token) >= 2 and token[0] in "\"'" and token[-1] == token[0]:
        return token[1:-1]
    try:
        return int(token)
    except ValueError:
        return token


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))
