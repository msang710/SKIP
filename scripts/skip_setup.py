#!/usr/bin/env python3
"""Shared SKIP rule configuration service for CLI and interactive clients."""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


DEFAULT_CORE_RULES = {
    "C-001": "Use explicit model language, otherwise current conversation language; preserve technical names.",
    "C-002": "Treat a user's FACT correction as a counterclaim and reinvestigate current evidence.",
    "C-003": "Return FACT corrected, existing FACT retained, or EVIDENCE_PENDING.",
    "C-004": "Split work at valid, testable system states.",
    "C-005": "Mark indivisible spans atomic and include containment and recovery.",
    "C-006": "Do not substitute one evidence surface for another.",
    "C-007": "Judge completion by the requested observable outcome.",
    "C-008": "Preserve NOT_RUN, partial verification, gaps, and EVIDENCE_PENDING.",
    "C-009": "Approval covers only the named artifact and scope.",
    "C-010": "Do not implicitly alter unrelated user work or records.",
}


class RuleConfigurationError(ValueError):
    pass


def json_record(path: Path, empty: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(empty)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuleConfigurationError(f"invalid JSON-compatible YAML record: {path}") from exc
    if not isinstance(value, dict):
        raise RuleConfigurationError(f"rule record must be a mapping: {path}")
    return value


def validate_core_config(
    value: dict[str, Any], validate_id: Callable[[str, str], str]
) -> dict[str, Any]:
    disabled = value.get("disabled_default_rule_ids", [])
    custom = value.get("custom_rules", [])
    if value.get("version", 1) != 1 or not isinstance(disabled, list) or not isinstance(custom, list):
        raise RuleConfigurationError("invalid Core rules configuration")
    if not all(item in DEFAULT_CORE_RULES for item in disabled):
        raise RuleConfigurationError("unknown disabled default Core rule")
    seen: set[str] = set()
    for rule in custom:
        if not isinstance(rule, dict):
            raise RuleConfigurationError("custom Core rule must be a mapping")
        if not all(rule.get(key) for key in ("id", "invariant", "detail", "status")):
            raise RuleConfigurationError("custom Core rule is missing a required field")
        authority = rule.get("authority")
        if not isinstance(authority, dict) or not authority.get("changed_at"):
            raise RuleConfigurationError("custom Core rule requires authority.changed_at")
        validate_id(str(rule["id"]), "custom Core rule id")
        if rule["id"] in seen or rule["id"] in DEFAULT_CORE_RULES:
            raise RuleConfigurationError("duplicate Core rule id")
        seen.add(rule["id"])
    return {"version": 1, "disabled_default_rule_ids": sorted(set(disabled)), "custom_rules": custom}


def validate_project_rules(
    value: dict[str, Any], project_id: str, validate_id: Callable[[str, str], str]
) -> dict[str, Any]:
    if value.get("version", 1) != 1 or value.get("project_id", project_id) != project_id:
        raise RuleConfigurationError("invalid Project Rules identity")
    rules = value.get("rules", [])
    if not isinstance(rules, list):
        raise RuleConfigurationError("Project Rules rules must be a list")
    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict) or not all(rule.get(key) for key in ("id", "rule", "scope", "status")):
            raise RuleConfigurationError("Project Rule is missing a required field")
        validate_id(str(rule["id"]), "Project Rule id")
        if rule["id"] in seen:
            raise RuleConfigurationError("duplicate Project Rule id")
        seen.add(rule["id"])
        authority = rule.get("authority")
        scope = rule.get("scope")
        if not isinstance(authority, dict) or not authority.get("changed_at"):
            raise RuleConfigurationError("Project Rule requires authority.changed_at")
        if not isinstance(scope, dict) or scope.get("kind") not in {"project", "environment-operation"}:
            raise RuleConfigurationError("invalid Project Rule scope")
        if scope["kind"] == "environment-operation" and not all(
            scope.get(key) for key in ("environment_id", "operation")
        ):
            raise RuleConfigurationError("environment-operation scope requires environment_id and operation")
    return {"version": 1, "project_id": project_id, "rules": rules}


def atomic_json_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    backup = path.with_suffix(path.suffix + ".bak")
    if path.exists():
        shutil.copy2(path, backup)
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


@dataclass(frozen=True)
class RulePaths:
    core: Path
    project: Path


class SetupService:
    def __init__(
        self,
        paths: RulePaths,
        project_id: str,
        validate_id: Callable[[str, str], str],
    ) -> None:
        self.paths = paths
        self.project_id = project_id
        self.validate_id = validate_id

    def load(self) -> tuple[dict[str, Any], dict[str, Any]]:
        core = validate_core_config(
            json_record(self.paths.core, {"version": 1, "disabled_default_rule_ids": [], "custom_rules": []}),
            self.validate_id,
        )
        project = validate_project_rules(
            json_record(self.paths.project, {"version": 1, "project_id": self.project_id, "rules": []}),
            self.project_id,
            self.validate_id,
        )
        return core, project

    def validate(
        self, core: dict[str, Any], project: dict[str, Any]
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        return (
            validate_core_config(core, self.validate_id),
            validate_project_rules(project, self.project_id, self.validate_id),
        )

    def apply(
        self,
        current: tuple[dict[str, Any], dict[str, Any]],
        proposed: tuple[dict[str, Any], dict[str, Any]],
    ) -> dict[str, bool]:
        current_core, current_project = current
        proposed_core, proposed_project = self.validate(*proposed)
        changes = {
            "core": proposed_core != current_core,
            "project": proposed_project != current_project,
        }
        if changes["core"]:
            atomic_json_write(self.paths.core, proposed_core)
        if changes["project"]:
            atomic_json_write(self.paths.project, proposed_project)
        return changes
