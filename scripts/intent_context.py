#!/usr/bin/env python3
"""Deterministically select SKIP records without third-party packages."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

# A direct script invocation and its libraries must share one selector class/state.
if __name__ == "__main__":
    sys.modules["intent_context"] = sys.modules[__name__]

if not __package__:
    from skip_setup import (
        DEFAULT_CORE_RULES,
        RuleConfigurationError,
        RulePaths,
        SetupService,
        json_record as json_record_shared,
        validate_core_config as validate_core_config_shared,
        validate_project_rules as validate_project_rules_shared,
    )
else:
    from scripts.skip_setup import (
        DEFAULT_CORE_RULES,
        RuleConfigurationError,
        RulePaths,
        SetupService,
        json_record as json_record_shared,
        validate_core_config as validate_core_config_shared,
        validate_project_rules as validate_project_rules_shared,
    )


SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RUNTIME_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
ARTIFACTS = {"impact", "prd", "user-stories", "user_stories", "system-design", "system_design", "tasks"}
PASEO_LOOKUP_TIMEOUT_SECONDS = 8
CONTEXT_STAGES = {
    "restore",
    "impact",
    "requirements",
    "design",
    "tasks",
    "implementation",
    "validation",
}
CONTEXT_FORMATS = {"json", "markdown"}
DEFAULT_CONTEXT_MAX_CHARS = 12_000
MIN_CONTEXT_MAX_CHARS = 2_000
SECTION_ALIASES = {
    "goal": {"목표", "Goal"},
    "facts": {"현재 사실", "Current facts"},
    "decisions": {"제품 결정", "Product decisions"},
    "requirements": {
        "제품 규칙",
        "요구사항",
        "수용 기준",
        "Product rules",
        "Requirements",
        "Acceptance criteria",
    },
    "design": {"목표 흐름", "시스템 설계", "Target flow", "Design"},
    "open_items": {
        "열린 질문",
        "불확실성",
        "열린 위험",
        "Open questions",
        "Uncertainty",
        "Open risks",
    },
    "human_review": {"Human Plan Review", "인간 계획 검토"},
}

STAGE_FIELDS = {
    "restore": {"facts", "confirmed_decisions", "requirements", "open_items"},
    "impact": {"facts", "open_items"},
    "requirements": {"facts", "confirmed_decisions", "requirements", "open_items"},
    "design": {"confirmed_decisions", "requirements", "design", "open_items"},
    "tasks": {"confirmed_decisions", "requirements", "design", "human_review", "tasks", "open_items"},
    "implementation": {
        "confirmed_decisions",
        "requirements",
        "design",
        "tasks",
        "human_review",
        "open_items",
    },
    "validation": {"facts", "open_items"},
}


class SelectionError(Exception):
    pass


@dataclass(frozen=True)
class ResolvedProject:
    root: Path
    root_source: str
    project_id: str
    project_dir: Path
    resolution_method: str | None
    paseo_project_id: str | None
    warnings: tuple[str, ...]


def platform_data_root() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if not base:
            raise SelectionError("LOCALAPPDATA is unavailable")
        return Path(base) / "SKIP"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SKIP"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "SKIP"


def platform_registry() -> Path:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA")
        if not base:
            raise SelectionError("APPDATA is unavailable")
        return Path(base) / "intent-to-code" / "workspaces.yaml"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "intent-to-code" / "workspaces.yaml"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "intent-to-code" / "workspaces.yaml"


def selected_record_root(args: argparse.Namespace) -> tuple[Path, str]:
    configured = os.environ.get("INTENT_TO_CODE_RECORD_ROOT", "").strip()
    root, source = ((Path(args.record_root).expanduser().resolve(), "explicit") if args.record_root else
                    (Path(configured).expanduser().resolve(), "environment") if configured else
                    (platform_data_root().expanduser().resolve(), "platform-default"))
    if (root / "skip.db").is_file():
        raise SelectionError("This record store uses SQLite Core. Use skip query/context/history; the file runtime is retired.")
    return root, source


def exact_date(value: str) -> str:
    if re.fullmatch(r"\d{6}", value):
        value = f"20{value[:2]}-{value[2:4]}-{value[4:]}"
    if not DATE_RE.fullmatch(value):
        raise SelectionError(f"invalid date: {value}")
    try:
        return dt.date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise SelectionError(f"invalid calendar date: {value}") from exc


def safe_slug(value: str, label: str) -> str:
    if not SLUG_RE.fullmatch(value):
        raise SelectionError(f"invalid {label}: {value}")
    return value


def resolve_beneath(root: Path, relative: Path) -> Path:
    root = root.expanduser().resolve()
    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise SelectionError(f"path escapes record root: {relative}") from exc
    return candidate


def yaml_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return None
    if value.startswith(("[", "{")):
        try:
            return json.loads(value)
        except json.JSONDecodeError as exc:
            raise SelectionError(f"invalid inline YAML value: {value}") from exc
    if value in {"true", "True"}:
        return True
    if value in {"false", "False"}:
        return False
    if value in {"null", "Null", "NULL", "~"}:
        return None
    return value.strip("\"'")


def nested_yaml(lines: list[str]) -> dict[str, Any]:
    """Parse SKIP's deterministic YAML subset: nested mappings and JSON-style values."""
    result: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, result)]
    for line_number, raw in enumerate(lines, start=2):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        if "\t" in raw[: len(raw) - len(raw.lstrip())]:
            raise SelectionError(f"frontmatter indentation must use spaces: line {line_number}")
        indent = len(raw) - len(raw.lstrip(" "))
        content = raw.strip()
        if content.startswith("-") or ":" not in content:
            raise SelectionError(f"unsupported structured frontmatter syntax: line {line_number}")
        key, raw_value = content.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
            raise SelectionError(f"invalid frontmatter key: line {line_number}")
        while stack[-1][0] >= indent:
            stack.pop()
        if indent > stack[-1][0] and stack[-1][0] >= 0 and indent - stack[-1][0] != 2:
            raise SelectionError(f"frontmatter indentation must increase by two: line {line_number}")
        parent = stack[-1][1]
        if key in parent:
            raise SelectionError(f"duplicate frontmatter key: {key}")
        if raw_value.strip():
            parent[key] = yaml_scalar(raw_value)
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
    return result


def frontmatter_text(text_value: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    lines = text_value.splitlines()
    if not lines or lines[0] != "---":
        return data
    body: list[str] = []
    terminated = False
    for line in lines[1:]:
        if line == "---":
            terminated = True
            break
        body.append(line)
    if not terminated:
        raise SelectionError("unterminated frontmatter")
    structured = any(re.match(r"^schema:\s*skip-artifact/v1\s*$", line.strip()) for line in body)
    if structured:
        return nested_yaml(body)
    for line in body:
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key.strip()):
            data[key.strip()] = value.strip().strip("\"'")
    return data


def frontmatter(path: Path) -> dict[str, Any]:
    try:
        return frontmatter_text(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise SelectionError(f"cannot read metadata: {path}: {exc}") from exc


def scalar_yaml(path: Path) -> dict[str, Any]:
    """Read the contract's shallow registry YAML subset."""
    result: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, result)]
    if not path.exists():
        return result
    raw_text = path.read_text(encoding="utf-8")
    if raw_text.lstrip().startswith("{"):
        try:
            value = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise SelectionError(f"invalid JSON-compatible YAML: {path}") from exc
        if not isinstance(value, dict):
            raise SelectionError(f"expected mapping: {path}")
        return value
    for raw in raw_text.splitlines():
        if not raw.strip() or raw.lstrip().startswith("#") or ":" not in raw:
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        key, value = raw.strip().split(":", 1)
        while stack[-1][0] >= indent:
            stack.pop()
        parent = stack[-1][1]
        value = value.strip().strip("\"'")
        if value:
            parent[key] = value
        else:
            child: dict[str, Any] = {}
            parent[key] = child
            stack.append((indent, child))
    return result


def normalize_remote(value: str) -> str:
    value = value.strip()
    if value.startswith("git@") and ":" in value:
        host, path = value[4:].split(":", 1)
        normalized = f"{host}/{path}"
    else:
        parsed = urlparse(value if "://" in value else f"https://{value}")
        host = parsed.hostname or ""
        normalized = f"{host}{parsed.path}"
    return normalized.rstrip("/").removesuffix(".git").lower()


def runtime_id(value: str, label: str) -> str:
    if not RUNTIME_ID_RE.fullmatch(value):
        raise SelectionError(f"invalid {label}: {value}")
    return value


def _git_output(workspace: Path, *arguments: str) -> str | None:
    try:
        proc = subprocess.run(["git", "-C", str(workspace), *arguments], text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                              check=False, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def git_root(workspace: Path) -> Path | None:
    value = _git_output(workspace, "rev-parse", "--show-toplevel")
    return Path(value).resolve() if value else None


def git_identity(workspace: Path) -> str | None:
    value = _git_output(workspace, "remote", "get-url", "origin")
    return normalize_remote(value) if value else None


def registry_projects(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    version = str(registry.get("version", "1"))
    if version not in {"1", "2"}:
        raise SelectionError(f"unsupported registry version: {version}")
    projects = registry.get("projects", {})
    if not isinstance(projects, dict):
        raise SelectionError("registry projects must be a mapping")
    normalized: dict[str, dict[str, Any]] = {}
    for project_id, entry in projects.items():
        safe_slug(project_id, "registry project id")
        if not isinstance(entry, dict):
            raise SelectionError(f"registry project entry must be a mapping: {project_id}")
        normalized[project_id] = entry
    return normalized


def paseo_bindings(registry: dict[str, Any], projects: dict[str, dict[str, Any]]) -> dict[str, str]:
    bindings = registry.get("bindings", {})
    if not isinstance(bindings, dict):
        raise SelectionError("registry bindings must be a mapping")
    paseo = bindings.get("paseo", {})
    if not isinstance(paseo, dict):
        raise SelectionError("registry bindings.paseo must be a mapping")
    normalized: dict[str, str] = {}
    for paseo_project_id, project_id in paseo.items():
        runtime_id(str(paseo_project_id), "Paseo project id")
        if not isinstance(project_id, str):
            raise SelectionError(f"Paseo binding must name a project: {paseo_project_id}")
        safe_slug(project_id, "Paseo binding project id")
        if project_id not in projects:
            raise SelectionError(
                f"Paseo binding references an unknown project: {paseo_project_id} -> {project_id}"
            )
        normalized[str(paseo_project_id)] = project_id
    return normalized


def project_repository_identities(project_id: str, entry: dict[str, Any]) -> set[str]:
    identities: set[str] = set()
    legacy = entry.get("repository_identity")
    if legacy:
        identities.add(normalize_remote(str(legacy)))
    sources = entry.get("sources", {})
    if not isinstance(sources, dict):
        raise SelectionError(f"registry project sources must be a mapping: {project_id}")
    for source_id, source in sources.items():
        safe_slug(source_id, "source id")
        if not isinstance(source, dict):
            raise SelectionError(f"registry source must be a mapping: {project_id}/{source_id}")
        source_root = source.get("source_root")
        if source_root:
            relative = Path(str(source_root))
            if relative.is_absolute() or ".." in relative.parts:
                raise SelectionError(
                    f"registry source_root must be workspace-relative: {project_id}/{source_id}"
                )
        configured = source.get("repository_identity")
        if configured:
            identities.add(normalize_remote(str(configured)))
    return identities


def declared_source_identity_matches(
    project_id: str,
    entry: dict[str, Any],
    workspace: Path,
) -> bool:
    sources = entry.get("sources", {})
    workspace_root = workspace.expanduser().resolve(strict=False)
    for source_id, source in sources.items():
        configured = source.get("repository_identity")
        if not configured:
            continue
        relative = Path(str(source.get("source_root", ".")))
        candidate = (workspace_root / relative).resolve(strict=False)
        try:
            candidate.relative_to(workspace_root)
        except ValueError as exc:
            raise SelectionError(
                f"registry source_root escapes runtime workspace: {project_id}/{source_id}"
            ) from exc
        if candidate.is_dir() and git_identity(candidate) == normalize_remote(str(configured)):
            return True
    return False


def paseo_cli() -> str | None:
    configured = os.environ.get("PASEO_CLI", "").strip()
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    return shutil.which("paseo")


def paseo_project_from_daemon(workspace: Path) -> tuple[str | None, list[str]]:
    configured = os.environ.get("PASEO_PROJECT_ID", "").strip()
    if configured:
        return runtime_id(configured, "Paseo project id"), [
            "Paseo project id supplied by the launch environment"
        ]
    ambient = any(
        os.environ.get(name)
        for name in ("PASEO_AGENT_ID", "PASEO_WORKSPACE_ID", "PASEO_AGENT_CWD")
    )
    if not ambient:
        return None, []
    command = paseo_cli()
    if not command:
        return None, ["Paseo project lookup unavailable: CLI not found"]
    try:
        result = subprocess.run(
            [command, "project", "ls", "--json"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=PASEO_LOOKUP_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None, ["Paseo project lookup unavailable: CLI invocation failed"]
    if result.returncode != 0:
        return None, [f"Paseo project lookup unavailable: CLI exited {result.returncode}"]
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, ["Paseo project lookup unavailable: malformed JSON"]
    if isinstance(payload, dict):
        payload = payload.get("projects")
    if not isinstance(payload, list):
        return None, ["Paseo project lookup unavailable: invalid project list"]

    resolved_workspace = workspace.expanduser().resolve(strict=False)
    matches: list[tuple[bool, int, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        raw_project_id = item.get("projectId")
        raw_path = item.get("path")
        if not isinstance(raw_project_id, str) or not isinstance(raw_path, str):
            continue
        runtime_id(raw_project_id, "Paseo project id")
        project_root = Path(raw_path).expanduser().resolve(strict=False)
        try:
            resolved_workspace.relative_to(project_root)
        except ValueError:
            continue
        matches.append(
            (resolved_workspace == project_root, len(project_root.parts), raw_project_id)
        )
    if not matches:
        return None, ["Paseo has no project containing the runtime workspace"]
    exact = [item for item in matches if item[0]]
    candidates = exact or [
        item for item in matches if item[1] == max(match[1] for match in matches)
    ]
    project_ids = sorted({item[2] for item in candidates})
    if len(project_ids) != 1:
        raise SelectionError("ambiguous Paseo project match for workspace")
    return project_ids[0], ["Paseo project id discovered from the daemon"]


def project_from_registry(
    registry_path: Path,
    workspace: Path,
    paseo_project_id: str | None = None,
) -> tuple[str | None, list[str], str | None]:
    registry = scalar_yaml(registry_path)
    projects = registry_projects(registry)
    bindings = paseo_bindings(registry, projects)
    root = git_root(workspace) or workspace.resolve()
    remote = git_identity(root)
    path_hits: list[str] = []
    remote_hits: list[str] = []
    for project_id, entry in projects.items():
        identities = project_repository_identities(project_id, entry)
        configured = entry.get("source_workspace")
        if configured and Path(str(configured)).expanduser().resolve() == root:
            path_hits.append(project_id)
        if (remote and remote in identities) or (
            not remote and declared_source_identity_matches(project_id, entry, workspace)
        ):
            remote_hits.append(project_id)
    if len(path_hits) > 1 or len(remote_hits) > 1:
        raise SelectionError("ambiguous project registry match")
    paseo_hit = bindings.get(paseo_project_id) if paseo_project_id else None
    selected = paseo_hit or (path_hits[0] if path_hits else (remote_hits[0] if remote_hits else None))
    warnings: list[str] = []
    if path_hits and remote_hits and path_hits[0] not in remote_hits:
        raise SelectionError("workspace path and repository identity conflict")
    observed_hits = set(path_hits + remote_hits)
    if paseo_hit and observed_hits and observed_hits != {paseo_hit}:
        raise SelectionError("Paseo project and repository registry identity conflict")
    if paseo_project_id and not paseo_hit:
        warnings.append(f"Paseo project id is not registered: {paseo_project_id}")
    if paseo_hit:
        warnings.append("project resolved by Paseo project id")
        method = "paseo-project-id"
    elif path_hits:
        warnings.append("project resolved by legacy absolute workspace path")
        method = "legacy-workspace-path"
    elif remote_hits:
        warnings.append("project resolved by repository identity")
        method = "repository-identity"
    else:
        method = None
    return selected, warnings, method


def contains_decisions(path: Path, decisions: list[str]) -> bool:
    if not decisions:
        return True
    metadata = frontmatter(path)
    if metadata.get("schema") == "skip-artifact/v1":
        decision_state = metadata.get("decisions", {})
        if not isinstance(decision_state, dict):
            raise SelectionError(f"structured decisions must be a mapping: {path}")
        known = decision_state.get("confirmed", []) + decision_state.get("open", [])
        if not isinstance(known, list) or not all(isinstance(item, str) for item in known):
            raise SelectionError(f"structured decision ids must be lists of strings: {path}")
        return all(item in known for item in decisions)
    text = path.read_text(encoding="utf-8", errors="replace")
    return all(re.search(rf"(?<![A-Za-z0-9_-]){re.escape(item)}(?![A-Za-z0-9_-])", text) for item in decisions)


def relative_manifest_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise SelectionError(f"selected path escapes record root: {path}") from exc


def selection_order(path: Path, root: Path) -> tuple[int, str]:
    relative = relative_manifest_path(path, root)
    rank = {
        "index.md": 0,
        "impact.md": 1,
        "prd.md": 2,
        "user_stories.md": 3,
        "system_design.md": 4,
        "tasks.md": 5,
        "system.md": 6,
        "validation.md": 7,
    }.get(path.name, 1)
    return rank, relative


def markdown_sections(text: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    heading: str | None = None
    content: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            if heading is not None:
                sections.append((heading, content))
            heading = match.group(1)
            content = []
        elif heading is not None:
            content.append(line)
    if heading is not None:
        sections.append((heading, content))
    return sections


def compact_lines(lines: list[str]) -> list[str]:
    return [line.strip() for line in lines if line.strip()]


def markdown_table_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [cell.strip() for cell in stripped[1:-1].split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def section_values(lines: list[str]) -> list[str]:
    table = markdown_table_rows(lines)
    if len(table) > 1:
        return [" | ".join(row) for row in table[1:]]
    return [value for value in compact_lines(lines) if value.casefold() not in {"없음.", "없음", "none.", "none"}]


def decision_values(lines: list[str]) -> tuple[list[str], list[str]]:
    table = markdown_table_rows(lines)
    if len(table) <= 1:
        return [], section_values(lines)
    header = [cell.casefold() for cell in table[0]]
    try:
        status_index = header.index("status")
    except ValueError:
        status_index = len(header) - 1
    confirmed: list[str] = []
    open_items: list[str] = []
    for row in table[1:]:
        rendered = " | ".join(row)
        status = row[status_index].casefold() if status_index < len(row) else ""
        if status in {"confirmed", "approved"}:
            confirmed.append(rendered)
        else:
            open_items.append(rendered)
    return confirmed, open_items


def projected_decision_ids(text: str) -> tuple[set[str], set[str]]:
    confirmed: set[str] = set()
    open_ids: set[str] = set()
    for line in text.splitlines():
        if not line.strip().startswith("|"):
            continue
        ids = re.findall(r"(?<![A-Za-z0-9_-])D-\d+(?![A-Za-z0-9_-])", line)
        if not ids:
            continue
        cells = [cell.strip().casefold() for cell in line.strip()[1:-1].split("|")]
        if any(cell in {"confirmed", "approved"} for cell in cells):
            confirmed.update(ids)
        elif any(cell == "open" for cell in cells):
            open_ids.update(ids)
    return confirmed, open_ids


def terminal_value(text: str, prefix: str) -> str | None:
    for line in reversed(text.splitlines()):
        stripped = line.strip()
        if stripped.startswith(prefix):
            return stripped[len(prefix) :].strip()
    return None


def restrictive_review(values: list[str]) -> str | None:
    if not values:
        return None
    if any(value.startswith("NEEDS_WORK") for value in values):
        return "NEEDS_WORK"
    if all(value.startswith("READY") for value in values):
        return "READY"
    return values[0]


def restrictive_gate(values: list[str]) -> str | None:
    if not values:
        return None
    if any(value.startswith("BLOCKED") for value in values):
        return "BLOCKED"
    if all(value.startswith("READY") for value in values):
        return "READY"
    return values[0]


def derived_goal(documents: list[str], explicit_goal: str | None) -> str | None:
    if explicit_goal:
        return explicit_goal
    goals: set[str] = set()
    for document in documents:
        parts = Path(document).parts
        if "features" in parts:
            index = parts.index("features")
            if index + 1 < len(parts):
                goals.add(parts[index + 1])
        if "goals" in parts and Path(document).suffix == ".md":
            index = parts.index("goals")
            if index + 1 < len(parts):
                goals.add(Path(parts[index + 1]).stem)
    return next(iter(goals)) if len(goals) == 1 else None


GOAL_ROUTING_ARTIFACTS = ("prd.md", "impact.md", "system_design.md", "tasks.md")
GOAL_STOP_TERMS = {
    "a",
    "an",
    "and",
    "for",
    "goal",
    "the",
    "to",
    "기능",
    "목표",
    "사용",
    "작업",
    "하는",
}
KOREAN_PARTICLE_SUFFIXES = ("으로", "에서", "에게", "부터", "까지", "은", "는", "이", "가", "을", "를", "의", "에", "와", "과", "로", "도")


def normalized_terms(value: str) -> tuple[str, list[str]]:
    folded = unicodedata.normalize("NFKC", value).casefold()
    normalized = " ".join(
        "".join(character if character.isalnum() else " " for character in folded).split()
    )
    terms: list[str] = []
    for original in normalized.split():
        term = original
        for suffix in KOREAN_PARTICLE_SUFFIXES:
            if term.endswith(suffix) and len(term) - len(suffix) >= 2:
                term = term[: -len(suffix)]
                break
        if len(term) >= 2 and term not in GOAL_STOP_TERMS:
            terms.append(term)
    return normalized, terms


def goal_summary(text_value: str) -> str | None:
    for heading, lines in markdown_sections(text_value):
        if heading in SECTION_ALIASES["goal"]:
            values = compact_lines(lines)
            return values[0] if values else None
    return None


def goal_candidates(resolved: ResolvedProject) -> list[dict[str, Any]]:
    project_dir = resolved.project_dir
    root = resolved.root
    inventory: dict[str, dict[str, Any]] = {}
    feature_root = project_dir / "features"
    if feature_root.is_dir():
        for directory in sorted(feature_root.iterdir(), key=lambda path: path.name):
            if directory.is_symlink():
                raise SelectionError(f"goal directory must not be a symlink: {directory.name}")
            if not directory.is_dir():
                continue
            slug = safe_slug(directory.name, "goal")
            inventory[slug] = {"slug": slug, "feature_dir": directory, "now_path": None}
    now_goal_root = project_dir / "NOW" / "goals"
    if now_goal_root.is_dir():
        for path in sorted(now_goal_root.iterdir(), key=lambda item: item.name):
            if path.is_symlink():
                raise SelectionError(f"NOW goal must not be a symlink: {path.name}")
            if not path.is_file() or path.suffix != ".md":
                continue
            slug = safe_slug(path.stem, "goal")
            candidate = inventory.setdefault(
                slug, {"slug": slug, "feature_dir": None, "now_path": None}
            )
            candidate["now_path"] = path
    candidates: list[dict[str, Any]] = []
    for slug in sorted(inventory):
        entry = inventory[slug]
        source: Path | None = None
        feature_dir = entry["feature_dir"]
        if feature_dir is not None:
            projection_path = feature_dir / ".skip" / "projection.yaml"
            if projection_path.is_file():
                try:
                    projection = json.loads(projection_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise SelectionError(f"invalid goal lifecycle projection: {slug}") from exc
                if projection.get("lifecycle") in {"revoked", "superseded"}:
                    continue
        if feature_dir is not None:
            for name in GOAL_ROUTING_ARTIFACTS:
                path = feature_dir / name
                if path.is_symlink():
                    raise SelectionError(f"goal routing document must not be a symlink: {slug}/{name}")
                if path.is_file():
                    source = path
                    break
        if source is None:
            source = entry["now_path"]
        try:
            text_value = source.read_text(encoding="utf-8", errors="replace") if source else ""
        except OSError as exc:
            raise SelectionError(f"cannot read goal routing document: {slug}: {exc}") from exc
        surface_lines = text_value.splitlines()
        if surface_lines and surface_lines[0] == "---" and "---" not in surface_lines[1:]:
            raise SelectionError(f"goal routing document has unterminated frontmatter: {slug}")
        metadata = frontmatter_text(text_value)
        if metadata.get("project_id") and metadata["project_id"] != resolved.project_id:
            raise SelectionError(f"goal routing document project mismatch: {slug}")
        if metadata.get("id") and metadata["id"] != slug:
            raise SelectionError(f"goal routing document id mismatch: {slug}")
        candidates.append(
            {
                "slug": slug,
                "title": metadata.get("title"),
                "summary": goal_summary(text_value) if source is not None else None,
                "evidence": [relative_manifest_path(source, root)] if source is not None else [],
            }
        )
    return candidates


def resolve_goal_query(args: argparse.Namespace) -> dict[str, Any]:
    resolved = resolve_project(args)
    query = args.query
    if args.stdin:
        query = sys.stdin.read()
    if not query or not query.strip():
        raise SelectionError("goal query must not be empty")
    query_normalized, query_terms = normalized_terms(query)
    query_term_set = set(query_terms)
    ranked: list[tuple[int, str, str, dict[str, Any]]] = []
    for candidate in goal_candidates(resolved):
        slug_normalized, slug_terms = normalized_terms(candidate["slug"])
        title_normalized, title_terms = normalized_terms(candidate.get("title") or "")
        summary_normalized, summary_terms = normalized_terms(candidate.get("summary") or "")
        padded_query = f" {query_normalized} "
        if slug_normalized and f" {slug_normalized} " in padded_query:
            ranked.append((4, "exact-slug", candidate["slug"], candidate))
            continue
        phrase_matches = [
            value
            for value, terms in ((title_normalized, title_terms), (summary_normalized, summary_terms))
            if value
            and len(terms) >= 2
            and (f" {value} " in padded_query or f" {query_normalized} " in f" {value} ")
        ]
        if phrase_matches:
            ranked.append((3, "exact-title", candidate["slug"], candidate))
            continue
        candidate_terms = set(slug_terms + title_terms + summary_terms)
        overlap = len(query_term_set & candidate_terms)
        if overlap:
            ranked.append((overlap, "unique-terms", candidate["slug"], candidate))
    # Phrase tiers outrank any number of incidental overlapping words.
    tiers = {"exact-slug": 3, "exact-title": 2, "unique-terms": 1}
    ranked.sort(key=lambda item: (-tiers[item[1]], -item[0], item[2]))
    status = "no_match"
    goal = None
    method = None
    output_candidates: list[dict[str, Any]] = []
    if ranked:
        best_score = ranked[0][0]
        best = [item for item in ranked if item[0] == best_score and item[1] == ranked[0][1]]
        if len(best) == 1 and (best_score >= 2 or best[0][1].startswith("exact-")):
            status = "resolved"
            goal = best[0][2]
            method = best[0][1]
            output_candidates = [best[0][3]]
        else:
            status = "ambiguous"
            output_candidates = [item[3] for item in best]
    for candidate in output_candidates:
        candidate.pop("summary", None)
    return {
        "schema": "goal-resolution/v1",
        "status": status,
        "project_id": resolved.project_id,
        "project_resolution": {
            "method": resolved.resolution_method,
            "paseo_project_id": resolved.paseo_project_id,
        },
        "record_root_source": resolved.root_source,
        "goal": goal,
        "method": method,
        "candidates": output_candidates,
        "warnings": list(resolved.warnings),
    }


def structured_artifact_state(metadata: dict[str, Any], path: str) -> dict[str, Any] | None:
    if metadata.get("schema") != "skip-artifact/v1":
        return None
    for key in ("artifact", "id", "project_id", "status"):
        if not isinstance(metadata.get(key), str) or not metadata[key]:
            raise SelectionError(f"structured artifact requires {key}: {path}")
    if metadata["status"] not in {"draft", "draft-with-open-questions", "approved"}:
        raise SelectionError(f"invalid structured artifact status: {path}")
    review = metadata.get("review")
    implementation = metadata.get("implementation")
    decisions = metadata.get("decisions", {"confirmed": [], "open": []})
    if not isinstance(review, dict) or review.get("verdict") not in {"ready", "needs-work"}:
        raise SelectionError(f"invalid structured review verdict: {path}")
    if not isinstance(implementation, dict) or implementation.get("gate") not in {"ready", "blocked"}:
        raise SelectionError(f"invalid structured implementation gate: {path}")
    if not isinstance(decisions, dict):
        raise SelectionError(f"structured decisions must be a mapping: {path}")
    confirmed = decisions.get("confirmed", [])
    open_ids = decisions.get("open", [])
    if not isinstance(confirmed, list) or not isinstance(open_ids, list):
        raise SelectionError(f"structured decision states must be lists: {path}")
    if not all(isinstance(item, str) and item for item in confirmed + open_ids):
        raise SelectionError(f"structured decision ids must be strings: {path}")
    if set(confirmed) & set(open_ids):
        raise SelectionError(f"structured decision cannot be confirmed and open: {path}")
    return {
        "review": review["verdict"].replace("-", "_").upper(),
        "gate": implementation["gate"].upper(),
        "confirmed": confirmed,
        "open": open_ids,
    }


def context_artifact(path: Path, relative: str, *, text_value: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if text_value is None:
        text_value = path.read_text(encoding="utf-8", errors="replace")
        metadata = frontmatter(path)
    else:
        metadata = frontmatter_text(text_value)
    semantic: dict[str, Any] = {
        "goal": [],
        "facts": [],
        "confirmed_decisions": [],
        "requirements": [],
        "design": [],
        "tasks": [],
        "human_review": [],
        "open_items": [],
    }
    for heading, lines in markdown_sections(text_value):
        if heading.startswith("T-") or re.match(r"^T-\d+\b", heading):
            semantic["tasks"].append(f"{heading}: {' '.join(compact_lines(lines))}")
            continue
        if heading in SECTION_ALIASES["goal"]:
            values = compact_lines(lines)
            if values:
                semantic["goal"].append(values[0])
        elif heading in SECTION_ALIASES["facts"]:
            semantic["facts"].extend(section_values(lines))
        elif heading in SECTION_ALIASES["decisions"]:
            confirmed, open_items = decision_values(lines)
            semantic["confirmed_decisions"].extend(confirmed)
            semantic["open_items"].extend(open_items)
        elif heading in SECTION_ALIASES["requirements"]:
            semantic["requirements"].extend(section_values(lines))
        elif heading in SECTION_ALIASES["design"]:
            semantic["design"].extend(section_values(lines))
        elif heading in SECTION_ALIASES["human_review"] and path.stem == "tasks":
            semantic["human_review"].extend(compact_lines(lines))
        elif heading in SECTION_ALIASES["open_items"]:
            semantic["open_items"].extend(section_values(lines))
    body_review = terminal_value(text_value, "Review verdict:")
    body_gate = terminal_value(text_value, "Implementation gate:")
    structured = structured_artifact_state(metadata, relative)
    if structured:
        review = structured["review"]
        gate = structured["gate"]
        if body_review and not body_review.startswith(review):
            raise SelectionError(f"structured review conflicts with Markdown projection: {relative}")
        if body_gate and not body_gate.startswith(gate):
            raise SelectionError(f"structured implementation gate conflicts with Markdown projection: {relative}")
        projected_confirmed, projected_open = projected_decision_ids(text_value)
        if projected_confirmed and projected_confirmed != set(structured["confirmed"]):
            raise SelectionError(f"structured decisions conflict with Markdown projection: {relative}")
        if projected_open and projected_open != set(structured["open"]):
            raise SelectionError(f"structured decisions conflict with Markdown projection: {relative}")
        semantic["confirmed_decisions"] = list(structured["confirmed"])
        semantic["open_items"].extend(f"{item}: open decision" for item in structured["open"])
    else:
        review = body_review
        gate = body_gate
    artifact = {
        "path": relative,
        "kind": metadata.get("artifact", path.stem),
        "status": metadata.get("status"),
        "title": metadata.get("title"),
        "project_id": metadata.get("project_id"),
        "source_revision": metadata.get("source_revision"),
        "review_verdict": review,
        "implementation_gate": gate,
        "metadata_source": "structured" if structured else "legacy",
        "input_chars": len(text_value),
        "input_bytes": len(text_value.encode("utf-8")),
    }
    return artifact, semantic


def semantic_text(value: Any) -> str:
    return value["text"] if isinstance(value, dict) else str(value)


def dedupe_semantic(values: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for value in values:
        marker = value["text"]
        if marker in seen:
            continue
        seen.add(marker)
        output.append(value)
    return output


def budget_pack(pack: dict[str, Any], max_chars: int) -> None:
    optional_fields = ["facts", "confirmed_decisions", "requirements", "design", "human_review", "tasks"]
    while len(json.dumps(pack, ensure_ascii=False, indent=2)) > max_chars:
        candidate = next((field for field in reversed(optional_fields) if pack.get(field)), None)
        if candidate is None:
            pack["status"] = "incomplete"
            pack["warnings"].append("non-droppable context exceeds --max-chars")
            return
        removed = pack[candidate].pop()
        expansion = {
            "field": candidate,
            "path": removed["path"] if isinstance(removed, dict) else None,
        }
        if expansion not in pack["required_expansions"]:
            pack["required_expansions"].append(expansion)


def render_context_markdown(pack: dict[str, Any]) -> str:
    lines = ["# Context Pack", "", "## Selection"]
    selection = pack["selection"]
    for key in ("project_id", "goal", "mode", "record_root_source", "source_verification"):
        lines.append(f"- {key}: {selection.get(key)}")
    sections = [
        ("Goal", "goal_summary"),
        ("Facts", "facts"),
        ("Confirmed decisions", "confirmed_decisions"),
        ("Requirements", "requirements"),
        ("Design", "design"),
        ("Tasks", "tasks"),
        ("Human Plan Review", "human_review"),
        ("Open items", "open_items"),
    ]
    for title, key in sections:
        values = pack.get(key)
        if not values:
            continue
        lines.extend(["", f"## {title}"])
        if isinstance(values, list):
            lines.extend(f"- {semantic_text(value)}" for value in values)
        else:
            lines.append(str(values))
    rules = pack.get("effective_rules", {})
    if rules:
        lines.extend(["", "## Effective rules"])
        if rules.get("default_core_rule_ids"):
            lines.append(f"- default Core: {', '.join(rules['default_core_rule_ids'])}")
        lines.extend(f"- {item['id']}: {item['invariant']}" for item in rules.get("custom_core_rules", []))
        lines.extend(f"- {item['id']}: {item['rule']}" for item in rules.get("project_rules", []))
    lines.extend(
        [
            "",
            "## Review and implementation gate",
            f"- review_verdict: {pack.get('review_verdict')}",
            f"- implementation_gate: {pack.get('implementation_gate')}",
            "",
            "## Required expansions",
        ]
    )
    expansions = pack.get("required_expansions", [])
    if expansions:
        lines.extend(f"- {item['field']}: {item.get('path')}" for item in expansions)
    else:
        lines.append("- none")
    lines.extend(["", "## Metrics"])
    lines.extend(f"- {key}: {value}" for key, value in pack["metrics"].items())
    return "\n".join(lines) + "\n"


def context_pack(args: argparse.Namespace, *, manifest: dict[str, Any] | None = None,
                 document_cache: Any = None, include_runtime: bool = True) -> dict[str, Any]:
    if args.max_chars < MIN_CONTEXT_MAX_CHARS:
        raise SelectionError(f"--max-chars must be at least {MIN_CONTEXT_MAX_CHARS}")
    manifest = select(args) if manifest is None else manifest
    if manifest["status"] != "selected":
        return manifest
    root = Path(manifest["record_root"]).resolve()
    documents = list(manifest["documents"])
    goal = derived_goal(documents, args.goal)
    effective_rules = effective_rule_manifest(
        root,
        manifest["project_id"],
        getattr(args, "environment_id", None),
        getattr(args, "operation", None),
    )
    artifacts: list[dict[str, Any]] = []
    combined = {
        "goal": [],
        "facts": [],
        "confirmed_decisions": [],
        "requirements": [],
        "design": [],
        "tasks": [],
        "human_review": [],
        "open_items": [],
    }
    review_values: list[str] = []
    gate_values: list[str] = []
    selected_chars = 0
    selected_bytes = 0
    for relative in documents:
        path = resolve_beneath(root, Path(relative))
        if not path.is_file():
            raise SelectionError(f"selected document is unavailable: {relative}")
        artifact, semantic = (context_artifact(path, relative) if document_cache is None else
                              document_cache.read(path, relative, context_artifact))
        if artifact["project_id"] and artifact["project_id"] != manifest["project_id"]:
            raise SelectionError(f"selected artifact project mismatch: {relative}")
        artifacts.append(artifact)
        selected_chars += artifact.pop("input_chars")
        selected_bytes += artifact.pop("input_bytes")
        if artifact["review_verdict"]:
            review_values.append(artifact["review_verdict"])
        if artifact["implementation_gate"]:
            gate_values.append(artifact["implementation_gate"])
        for key in combined:
            combined[key].extend(
                {"text": value, "path": relative} for value in semantic[key]
            )
    stage_fields = STAGE_FIELDS[args.stage]
    for key in combined:
        combined[key] = dedupe_semantic(combined[key])
    review = restrictive_review(review_values)
    gate = restrictive_gate(gate_values)
    warnings = list(manifest["warnings"])
    required_expansions: list[dict[str, str]] = []
    status = "complete"
    gate_required = args.stage in {"requirements", "design", "tasks", "implementation"}
    if gate_required and (review is None or gate is None):
        status = "incomplete"
        warnings.append("required review verdict or implementation gate is missing")
        for artifact in artifacts:
            if not artifact["review_verdict"] or not artifact["implementation_gate"]:
                required_expansions.append({"path": artifact["path"], "field": "review-gate"})
    if args.stage in {"tasks", "implementation"} and goal is None:
        status = "incomplete"
        warnings.append("goal is required for tasks or implementation context")
    pack: dict[str, Any] = {
        "schema": "context-pack/v1",
        "status": status,
        "stage": args.stage,
        "selection": {
            "project_id": manifest["project_id"],
            "goal": goal,
            "mode": manifest["mode"],
            "record_root_source": manifest["record_root_source"],
            "documents": documents,
            "source_verification": manifest["source_verification"],
            "warnings": list(manifest["warnings"]),
        },
        "artifacts": artifacts,
        "goal_summary": semantic_text(combined["goal"][0]) if combined["goal"] else None,
        "facts": combined["facts"] if "facts" in stage_fields else [],
        "confirmed_decisions": (
            combined["confirmed_decisions"] if "confirmed_decisions" in stage_fields else []
        ),
        "requirements": combined["requirements"] if "requirements" in stage_fields else [],
        "design": combined["design"] if "design" in stage_fields else [],
        "tasks": combined["tasks"] if "tasks" in stage_fields else [],
        "human_review": combined["human_review"] if "human_review" in stage_fields else [],
        "open_items": combined["open_items"] if "open_items" in stage_fields else [],
        "review_verdict": review,
        "implementation_gate": gate,
        "effective_rules": effective_rules,
        "required_expansions": required_expansions,
        "warnings": warnings,
        "metrics": {
            "selected_input_chars": selected_chars,
            "selected_input_bytes": selected_bytes,
            "pack_chars": 0,
            "pack_bytes": 0,
            "selected_document_count": len(documents),
            "required_expansion_count": len(required_expansions),
        },
    }
    if goal and include_runtime:
        project_dir = resolve_beneath(root, Path("projects") / manifest["project_id"])
        state_dir = resolve_beneath(project_dir, Path("features") / goal / ".skip")
        if state_dir.is_dir():
            runtime = decision_runtime_for(
                argparse.Namespace(**{**vars(args), "project": manifest["project_id"], "record_root": str(root), "goal": goal})
            )
            projection = runtime.replay()
            pack["goal_lifecycle"] = projection["lifecycle"]
            pack["decision_inbox"] = runtime.inbox()
            pack["action_gates"] = {action: runtime.evaluate_gate(action) for action in ("requirements", "design", "tasks", "implement", "validate", "deploy")}
    budget_pack(pack, args.max_chars)
    pack["metrics"]["required_expansion_count"] = len(pack["required_expansions"])
    for _ in range(4):
        rendered = json.dumps(pack, ensure_ascii=False, indent=2)
        chars = len(rendered)
        byte_count = len(rendered.encode("utf-8"))
        if (
            pack["metrics"]["pack_chars"] == chars
            and pack["metrics"]["pack_bytes"] == byte_count
        ):
            break
        pack["metrics"]["pack_chars"] = chars
        pack["metrics"]["pack_bytes"] = byte_count
    if len(json.dumps(pack, ensure_ascii=False, indent=2)) > args.max_chars:
        budget_pack(pack, args.max_chars)
        rendered = json.dumps(pack, ensure_ascii=False, indent=2)
        pack["metrics"]["pack_chars"] = len(rendered)
        pack["metrics"]["pack_bytes"] = len(rendered.encode("utf-8"))
    return pack


def resolve_project(args: argparse.Namespace) -> ResolvedProject:
    root, root_source = selected_record_root(args)
    registry = Path(args.registry or platform_registry()).expanduser()
    warnings: list[str] = []
    project_id = args.project
    workspace = Path(args.workspace or os.getcwd()).expanduser()
    resolution_method = "explicit-project" if project_id else None
    paseo_project_id = None
    if project_id:
        safe_slug(project_id, "project id")
    else:
        if args.paseo_project_id:
            paseo_project_id = runtime_id(args.paseo_project_id, "Paseo project id")
        else:
            paseo_project_id, paseo_warnings = paseo_project_from_daemon(workspace)
            warnings.extend(paseo_warnings)
        project_id, registry_warnings, resolution_method = project_from_registry(
            registry,
            workspace,
            paseo_project_id,
        )
        warnings.extend(registry_warnings)
    if not project_id:
        detail = f"; {'; '.join(warnings)}" if warnings else ""
        raise SelectionError(
            "project could not be resolved; provide --project or register a runtime identity"
            f"{detail}"
        )

    project_dir = resolve_beneath(root, Path("projects") / project_id)
    if (project_dir / ".bootstrap-pending").exists():
        raise SelectionError("project bootstrap is incomplete; recover its transaction first")
    if not project_dir.is_dir():
        raise SelectionError(f"record project does not exist: {project_id}")
    project_file = project_dir / "project.yaml"
    if project_file.is_file():
        declared = scalar_yaml(project_file).get("project_id")
        if declared and declared != project_id:
            raise SelectionError(f"project identity mismatch: requested {project_id}, declared {declared}")

    return ResolvedProject(
        root=root,
        root_source=root_source,
        project_id=project_id,
        project_dir=project_dir,
        resolution_method=resolution_method,
        paseo_project_id=paseo_project_id,
        warnings=tuple(warnings),
    )


def resolve(args: argparse.Namespace) -> dict[str, Any]:
    resolved = resolve_project(args)
    return {
        "status": "resolved",
        "mode": "identity",
        "project_id": resolved.project_id,
        "project_resolution": {
            "method": resolved.resolution_method,
            "paseo_project_id": resolved.paseo_project_id,
        },
        "record_root": str(resolved.root),
        "record_root_source": resolved.root_source,
        "documents": [],
        "source_verification": "not-requested",
        "warnings": list(resolved.warnings),
    }


def select(args: argparse.Namespace) -> dict[str, Any]:
    resolved = resolve_project(args)
    root = resolved.root
    project_id = resolved.project_id
    project_dir = resolved.project_dir

    date = exact_date(args.date) if args.date else None
    updated = exact_date(args.updated) if args.updated else None
    if args.now and (date or updated) and not args.compare:
        raise SelectionError("--now and date filters require --compare")
    if args.compare and not (args.now and (date or updated)):
        raise SelectionError("--compare requires --now and a date filter")
    goal = safe_slug(args.goal, "goal") if args.goal else None
    artifacts = []
    if args.artifacts:
        for item in args.artifacts.split(","):
            normalized = item.strip().lower()
            if normalized not in ARTIFACTS:
                raise SelectionError(f"unsupported artifact: {item}")
            artifacts.append(normalized.replace("-", "_"))
    decisions = [item.strip() for item in (args.decision or "").split(",") if item.strip()]
    mode = "compare" if args.compare and args.now and (date or updated) else ("now" if args.now else "historical")
    selected: list[Path] = []

    if args.now:
        now_root = resolve_beneath(project_dir, Path("NOW"))
        candidates: list[Path] = []
        index = now_root / "index.md"
        if index.is_file():
            candidates.append(index)
        for shared_name in ("system.md", "validation.md"):
            shared = now_root / shared_name
            if shared.is_file():
                candidates.append(shared)
        if goal:
            goal_path = resolve_beneath(now_root, Path("goals") / f"{goal}.md")
            if goal_path.is_file():
                candidates.append(goal_path)
        if args.focus == "decisions":
            candidates = [path for path in candidates if path.name == "index.md" or "Product behavior in force" in path.read_text(encoding="utf-8", errors="replace")]
        selected.extend(path for path in candidates if contains_decisions(path, decisions))

    if not args.now or args.compare:
        feature_root = resolve_beneath(project_dir, Path("features") / goal) if goal else resolve_beneath(project_dir, Path("features"))
        candidates = list(feature_root.rglob("*.md")) if feature_root.is_dir() else []
        for path in candidates:
            artifact_name = path.stem
            if artifacts and artifact_name not in artifacts:
                continue
            meta = frontmatter(path)
            if date and meta.get("created") != date:
                if not (args.include_undated and not meta.get("created")):
                    continue
            if updated and meta.get("updated") != updated:
                continue
            if args.focus == "decisions" and artifact_name not in {"prd", "user_stories", "system_design"}:
                continue
            if not contains_decisions(path, decisions):
                continue
            selected.append(path)

    unique = sorted({path.resolve() for path in selected}, key=lambda path: selection_order(path, root))
    return {
        "status": "selected" if unique else "no_match",
        "mode": mode,
        "project_id": project_id,
        "project_resolution": {
            "method": resolved.resolution_method,
            "paseo_project_id": resolved.paseo_project_id,
        },
        "record_root": str(root),
        "record_root_source": resolved.root_source,
        "documents": [relative_manifest_path(path, root) for path in unique],
        "source_verification": "required" if args.verify or args.now else "stage-dependent",
        "warnings": list(resolved.warnings),
    }


def json_record(path: Path, empty: dict[str, Any]) -> dict[str, Any]:
    try:
        return json_record_shared(path, empty)
    except RuleConfigurationError as exc:
        raise SelectionError(str(exc)) from exc


def validate_core_config(value: dict[str, Any]) -> dict[str, Any]:
    try:
        return validate_core_config_shared(value, runtime_id)
    except RuleConfigurationError as exc:
        raise SelectionError(str(exc)) from exc


def validate_project_rules(value: dict[str, Any], project_id: str) -> dict[str, Any]:
    try:
        return validate_project_rules_shared(value, project_id, runtime_id)
    except RuleConfigurationError as exc:
        raise SelectionError(str(exc)) from exc


def effective_rule_manifest(
    root: Path,
    project_id: str,
    environment_id: str | None = None,
    operation: str | None = None,
) -> dict[str, Any]:
    core_path = resolve_beneath(root, Path("config/core-rules.yaml"))
    project_path = resolve_beneath(root, Path("projects") / project_id / "project-rules.yaml")
    core = validate_core_config(json_record(core_path, {"version": 1, "disabled_default_rule_ids": [], "custom_rules": []}))
    project = validate_project_rules(json_record(project_path, {"version": 1, "project_id": project_id, "rules": []}), project_id)
    disabled = set(core["disabled_default_rule_ids"])
    active_default_ids = [rule_id for rule_id in DEFAULT_CORE_RULES if rule_id not in disabled]
    active_custom = [
        {"id": rule["id"], "invariant": rule["invariant"], "provenance": "user"}
        for rule in core["custom_rules"]
        if rule["status"] == "active"
    ]
    selected_project: list[dict[str, Any]] = []
    withheld: list[str] = []
    for rule in project["rules"]:
        if rule["status"] != "active":
            continue
        scope = rule["scope"]
        if scope["kind"] == "project":
            selected_project.append(rule)
        elif environment_id == scope["environment_id"] and operation == scope["operation"]:
            selected_project.append(rule)
        else:
            withheld.append(rule["id"])
    return {
        "schema": "skip-rules/v1",
        "default_core_rule_ids": active_default_ids,
        "custom_core_rules": active_custom,
        "disabled_default_rule_ids": sorted(disabled),
        "project_rules": selected_project,
        "withheld_environment_rule_ids": withheld,
    }


def json_argument(value: str, label: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SelectionError(f"invalid {label} JSON") from exc
    if not isinstance(parsed, dict):
        raise SelectionError(f"{label} must be a JSON object")
    return parsed


def setup_rules(args: argparse.Namespace) -> dict[str, Any]:
    resolved = resolve_project(args)
    root = resolved.root
    core_path = resolve_beneath(root, Path("config/core-rules.yaml"))
    project_path = resolve_beneath(root, Path("projects") / resolved.project_id / "project-rules.yaml")
    service = SetupService(RulePaths(core_path, project_path), resolved.project_id, runtime_id)
    try:
        current_core, current_project = service.load()
    except RuleConfigurationError as exc:
        raise SelectionError(str(exc)) from exc
    proposed_core = json.loads(json.dumps(current_core))
    proposed_project = json.loads(json.dumps(current_project))
    disabled = set(proposed_core["disabled_default_rule_ids"])
    for rule_id in args.disable or []:
        if rule_id not in DEFAULT_CORE_RULES:
            raise SelectionError(f"unknown default Core rule: {rule_id}")
        disabled.add(rule_id)
    for rule_id in args.enable or []:
        disabled.discard(rule_id)
    proposed_core["disabled_default_rule_ids"] = sorted(disabled)
    remove_custom = set(args.remove_custom_rule or [])
    remove_project = set(args.remove_project_rule or [])
    proposed_core["custom_rules"] = [rule for rule in proposed_core["custom_rules"] if rule.get("id") not in remove_custom]
    proposed_project["rules"] = [rule for rule in proposed_project["rules"] if rule.get("id") not in remove_project]
    proposed_core["custom_rules"].extend(json_argument(item, "custom rule") for item in args.custom_rule or [])
    proposed_project["rules"].extend(json_argument(item, "project rule") for item in args.project_rule or [])
    proposed_core = validate_core_config(proposed_core)
    proposed_project = validate_project_rules(proposed_project, resolved.project_id)
    changed_core = proposed_core != current_core
    changed_project = proposed_project != current_project
    if args.apply:
        try:
            service.apply((current_core, current_project), (proposed_core, proposed_project))
        except RuleConfigurationError as exc:
            raise SelectionError(str(exc)) from exc
    return {
        "schema": "skip-setup/v1",
        "status": "applied" if args.apply else "preview",
        "project_id": resolved.project_id,
        "record_root": str(root),
        "changes": {"core": changed_core, "project": changed_project},
        "effective": effective_rule_manifest(root, resolved.project_id, args.environment_id, args.operation)
        if args.apply
        else {
            "current": effective_rule_manifest(root, resolved.project_id, args.environment_id, args.operation),
            "proposed_core": proposed_core,
            "proposed_project": proposed_project,
        },
    }


def add_identity_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--record-root", help="override the external record-store root")
    command.add_argument("--registry", help="override the local workspace registry")
    command.add_argument("--project", metavar="ID", help="select a registered record project")
    command.add_argument(
        "--workspace",
        metavar="PATH",
        help="resolve the project from a runtime workspace",
    )
    command.add_argument(
        "--paseo-project-id",
        metavar="ID",
        help="resolve the project from a registered Paseo project id",
    )


def add_selection_arguments(command: argparse.ArgumentParser) -> None:
    command.add_argument("--now", action="store_true", help="select current-state records only")
    command.add_argument("--date", metavar="DATE", help="match an exact artifact created date")
    command.add_argument("--updated", metavar="DATE", help="match an exact artifact updated date")
    command.add_argument("--goal", metavar="SLUG", help="limit selection to one goal")
    command.add_argument(
        "--artifacts",
        metavar="LIST",
        help="limit selection to comma-separated artifact types",
    )
    command.add_argument(
        "--focus",
        choices=["decisions"],
        help="prefer decision-bearing records",
    )
    command.add_argument(
        "--decision",
        metavar="IDS",
        help="require comma-separated decision ids",
    )
    command.add_argument("--verify", action="store_true", help="require source freshness checks")
    command.add_argument(
        "--compare",
        action="store_true",
        help="allow NOW and historical date selection together",
    )
    command.add_argument(
        "--include-undated",
        action="store_true",
        help="include historical records without a created date",
    )


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    command = commands.add_parser(
        "select",
        help="select a bounded record set",
        description=(
            "Select a bounded SKIP record set. --help exits before project "
            "resolution or record access."
        ),
    )
    add_identity_arguments(command)
    add_selection_arguments(command)
    context = commands.add_parser(
        "context",
        help="compile a bounded Context Pack from selected records",
        description=(
            "Select records with the canonical selector, then compile a deterministic "
            "read-only Context Pack. --help exits before project resolution or record access."
        ),
    )
    add_identity_arguments(context)
    add_selection_arguments(context)
    context.add_argument("--stage", choices=sorted(CONTEXT_STAGES), required=True)
    context.add_argument("--format", choices=sorted(CONTEXT_FORMATS), default="json")
    context.add_argument("--max-chars", type=int, default=DEFAULT_CONTEXT_MAX_CHARS)
    context.add_argument("--environment-id", help="select matching environment-scoped Project Rules")
    context.add_argument("--operation", help="select matching operation-scoped Project Rules")
    commands.add_parser("entry", help="minimal shared entry; run entry --help for options")
    commands.add_parser("prepare-v2", help="risk-adaptive shared entry; run prepare-v2 --help")
    prepare = commands.add_parser("prepare", help="prepare a read-only workflow plan; never approve or execute writes")
    add_identity_arguments(prepare)
    add_selection_arguments(prepare)
    prepare.add_argument("--stage", choices=sorted(CONTEXT_STAGES), required=True)
    prepare.add_argument("--request-file", required=True, help="workflow-request/v1 JSON file, or - for stdin")
    prepare.add_argument("--max-chars", type=int, default=DEFAULT_CONTEXT_MAX_CHARS)
    prepare.add_argument("--environment-id")
    report = commands.add_parser("report", help="render supplied workflow evidence without executing validation")
    report.add_argument("--result-file", required=True, help="workflow-result/v1 JSON file, or - for stdin")
    report.add_argument("--format", choices=["json", "brief", "detail"], default="brief")
    resolver = commands.add_parser(
        "resolve",
        help="resolve project identity without selecting records (provider hook internal)",
    )
    add_identity_arguments(resolver)
    goals = commands.add_parser(
        "goals",
        help="resolve a natural-language request to one bounded existing goal",
        description=(
            "Resolve one existing goal from bounded project metadata. --help exits before "
            "project resolution or record access."
        ),
    )
    add_identity_arguments(goals)
    query_input = goals.add_mutually_exclusive_group(required=True)
    query_input.add_argument("--query", help="natural-language request for local debugging")
    query_input.add_argument(
        "--stdin",
        action="store_true",
        help="read the natural-language request from standard input without echoing it",
    )
    setup = commands.add_parser(
        "setup",
        help="preview or apply explicitly approved Core and Project Rule changes",
    )
    add_identity_arguments(setup)
    setup.add_argument("--disable", action="append", help="disable one bundled Core rule ID")
    setup.add_argument("--enable", action="append", help="re-enable one bundled Core rule ID")
    setup.add_argument("--custom-rule", action="append", help="append one custom Core rule JSON object")
    setup.add_argument("--project-rule", action="append", help="append one Project Rule JSON object")
    setup.add_argument("--remove-custom-rule", action="append", help="remove one custom Core rule ID")
    setup.add_argument("--remove-project-rule", action="append", help="remove one Project Rule ID")
    setup.add_argument("--environment-id", help="preview an environment-scoped rule selection")
    setup.add_argument("--operation", help="preview an operation-scoped rule selection")
    setup.add_argument("--apply", action="store_true", help="apply the exact previewed change after user approval")
    for name, help_text in (
        ("inbox", "read the goal Decision Inbox"),
        ("gate", "evaluate one goal action gate"),
        ("history", "read bounded goal authority history"),
        ("runtime-init", "explicitly initialize decision runtime for one goal"),
    ):
        runtime_command = commands.add_parser(name, help=help_text)
        add_identity_arguments(runtime_command)
        runtime_command.add_argument("--goal", required=True)
        if name == "gate":
            runtime_command.add_argument("--action", required=True, choices=["requirements", "design", "tasks", "implement", "validate", "deploy"])
        if name == "history":
            runtime_command.add_argument("--limit", type=int, default=50)
    mutation = commands.add_parser("mutation", help="preview an allowlisted goal mutation")
    add_identity_arguments(mutation)
    mutation.add_argument("--goal", required=True)
    mutation.add_argument("--command-file", required=True, help="JSON-compatible YAML mutation command, or - for stdin")
    allow = commands.add_parser("allow", help="commit an exact preview with user-origin authority")
    add_identity_arguments(allow)
    allow.add_argument("--goal", required=True)
    allow.add_argument("--command-file", required=True, help="exact previewed mutation command")
    allow.add_argument("--request-id", required=True)
    allow.add_argument("--authority-kind", required=True, choices=["user_turn", "interactive_cli", "native_user_action", "agent_proposal"])
    allow.add_argument("--host")
    return root


def decision_runtime_for(args: argparse.Namespace) -> Any:
    if not __package__:
        from decision_runtime import DecisionRuntime
    else:
        from scripts.decision_runtime import DecisionRuntime
    resolved = resolve_project(args)
    return DecisionRuntime(resolved.project_dir, resolved.project_id, safe_slug(args.goal, "goal"))


def command_object(path_value: str) -> dict[str, Any]:
    raw = sys.stdin.read() if path_value == "-" else Path(path_value).read_text(encoding="utf-8")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SelectionError("mutation command must be JSON-compatible YAML") from exc
    if not isinstance(value, dict):
        raise SelectionError("mutation command must be an object")
    return value


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if len(sys.argv) > 1 and sys.argv[1] in {"entry", "prepare-v2"}:
        if not __package__:
            from workflow_entry import main as entry_main
        else:
            from scripts.workflow_entry import main as entry_main
        return entry_main(sys.argv[2:])
    args = parser().parse_args()
    try:
        if args.command in {"prepare", "report"}:
            if not __package__:
                from workflow_runtime import prepare_workflow
                from workflow_report import validate_result, render_brief, render_detail
            else:
                from scripts.workflow_runtime import prepare_workflow
                from scripts.workflow_report import validate_result, render_brief, render_detail
            if args.command == "prepare":
                result = prepare_workflow(args, command_object(args.request_file))
                print(json.dumps(result, ensure_ascii=False, indent=2))
                return 0 if result["status"] == "prepared" else (3 if result["status"] == "no_match" else 2)
            result = validate_result(command_object(args.result_file))
            if args.format == "json":
                print(json.dumps(result, ensure_ascii=False, indent=2))
            else:
                print((render_brief if args.format == "brief" else render_detail)(result), end="")
            return 0
        if args.command == "resolve":
            result = resolve(args)
        elif args.command == "goals":
            result = resolve_goal_query(args)
        elif args.command == "setup":
            result = setup_rules(args)
        elif args.command == "context":
            result = context_pack(args)
        elif args.command == "runtime-init":
            result = decision_runtime_for(args).initialize()
        elif args.command == "inbox":
            result = decision_runtime_for(args).inbox()
        elif args.command == "gate":
            result = decision_runtime_for(args).evaluate_gate(args.action)
        elif args.command == "history":
            result = decision_runtime_for(args).history(args.limit)
        elif args.command == "mutation":
            result = decision_runtime_for(args).preview(command_object(args.command_file))
        elif args.command == "allow":
            result = decision_runtime_for(args).allow(
                command_object(args.command_file),
                {"schema": "authority-envelope/v1", "kind": args.authority_kind,
                 "request_id": args.request_id, "host": args.host},
            )
        else:
            result = select(args)
        if args.command == "context" and args.format == "markdown" and result.get("schema"):
            print(render_context_markdown(result), end="")
        else:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] in {"selected", "resolved", "complete", "preview", "applied", "ok", "initialized", "PENDING", "COMMITTED", "ALLOW"}:
            return 0
        return 3 if result["status"] == "no_match" else 2
    except SelectionError as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    except Exception as exc:
        if hasattr(exc, "error_code"):
            print(json.dumps({"status": "error", "error_code": exc.error_code,
                              "operation": args.command, "error": str(exc),
                              "retryable": getattr(exc, "retryable", False)}, ensure_ascii=False, indent=2))
            return 2
        print(
            json.dumps(
                {
                    "status": "error",
                    "error_code": "internal_tool_error",
                    "operation": args.command,
                    "error": "unexpected internal tool failure",
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
