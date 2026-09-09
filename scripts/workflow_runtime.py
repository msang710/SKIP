"""Read-only workflow preparation over the canonical selector and decision engine."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any

try:
    import intent_context as context
    from context_session import DocumentCache, SessionContext, fingerprint
    from decision_runtime import DecisionRuntime, DecisionRuntimeError
    from workflow_report import WorkflowError, strings
except ModuleNotFoundError:
    from scripts import intent_context as context
    from scripts.context_session import DocumentCache, SessionContext, fingerprint
    from scripts.decision_runtime import DecisionRuntime, DecisionRuntimeError
    from scripts.workflow_report import WorkflowError, strings


RISK_FLAGS = {"permissions", "persisted_data", "money", "state_transition", "integration",
              "destructive", "difficult_rollback", "unknown"}
OPERATIONS = {"answer", "plan", "implement", "validate", "deploy"}
STAGES = {"answer": {"restore", "impact"}, "plan": {"impact", "requirements", "design", "tasks"},
          "implement": {"implementation"}, "validate": {"validation"}, "deploy": {"validation"}}


def validate_request(value: Any, stage: str) -> dict[str, Any]:
    required = {"schema", "requested_operation", "requested_depth", "scope"}
    allowed = required | {"query", "records_required", "source_evidence"}
    if not isinstance(value, dict) or required - set(value) or set(value) - allowed:
        raise WorkflowError("invalid workflow request fields")
    if value["schema"] != "workflow-request/v1":
        raise WorkflowError("expected workflow-request/v1")
    operation = value["requested_operation"]
    if not isinstance(operation, str) or operation not in OPERATIONS or stage not in STAGES[operation]:
        raise WorkflowError("requested operation conflicts with stage")
    depth = value["requested_depth"]
    if not isinstance(depth, str) or depth not in {"auto", "answer", "compact", "full"} or (depth == "answer" and operation != "answer"):
        raise WorkflowError("invalid requested depth")
    scope = value["scope"]
    if not isinstance(scope, dict) or set(scope) != {"behavior_change", "risk_flags", "evidence_refs"}:
        raise WorkflowError("scope requires behavior_change, risk_flags, evidence_refs")
    if not isinstance(scope["behavior_change"], str) or scope["behavior_change"] not in {"yes", "no", "unknown"}:
        raise WorkflowError("invalid behavior_change")
    if set(strings(scope["risk_flags"], "risk_flags")) - RISK_FLAGS:
        raise WorkflowError("unsupported risk flag")
    strings(scope["evidence_refs"], "evidence_refs")
    if "query" in value and (not isinstance(value["query"], str) or not value["query"].strip()):
        raise WorkflowError("query must be a nonempty string")
    if type(value.get("records_required", True)) is not bool:
        raise WorkflowError("records_required must be boolean")
    if not value.get("records_required", True) and operation != "answer":
        raise WorkflowError("only self-contained answers may omit records")
    if "source_evidence" in value:
        evidence = value["source_evidence"]
        if not isinstance(evidence, dict) or set(evidence) != {"snapshot_digest"}:
            raise WorkflowError("source_evidence requires snapshot_digest")
        token = evidence["snapshot_digest"]
        if not isinstance(token, str) or len(token) != 64 or any(c not in "0123456789abcdef" for c in token):
            raise WorkflowError("invalid source snapshot digest")
    return value


def classify_depth(request: dict[str, Any]) -> str:
    if request["requested_operation"] == "answer":
        return "answer"
    scope = request["scope"]
    if (request["requested_depth"] == "full" or scope["behavior_change"] != "no" or
            scope["risk_flags"] or not scope["evidence_refs"]):
        return "full"
    return "compact"


def choose_next_action(request: dict[str, Any], pack: dict[str, Any], authorization: dict[str, Any],
                       source_status: str) -> str:
    operation = request["requested_operation"]
    if pack.get("status") != "complete" or pack.get("required_expansions"):
        return "expand_context"
    if operation == "answer":
        return "answer"
    if operation == "plan":
        return "present_plan"  # Read-only drafts retain the separate, possibly blocked action gate.
    if authorization["status"] == "STALE":
        return "verify" if "VALIDATION_EVIDENCE_STALE" in authorization["reasons"] else "revise_artifact"
    if authorization["status"] != "ALLOW":
        reasons = authorization["reasons"]
        if "CAPABILITY_UNAVAILABLE" in reasons or "GOAL_NOT_ACTIVE" in reasons:
            return "stop"
        if any("VALIDATION_EVIDENCE" in reason for reason in reasons):
            return "verify"
        if any(reason.startswith("MISSING_") or reason.endswith("_NOT_READY") or
               reason == "OPEN_PRODUCT_DECISIONS" for reason in reasons):
            return "revise_artifact"
        return "request_approval"
    if (source_status != "CURRENT_SOURCE_ONLY" or
            request["scope"]["behavior_change"] == "unknown" or "unknown" in request["scope"]["risk_flags"]):
        return "inspect_source"
    if operation == "implement":
        return "implement"
    if operation == "validate":
        return "verify"
    return "stop"  # First release never dispatches deployment.


def source_snapshot(workspace: Path, references: list[str]) -> dict[str, Any]:
    """Measure current files/dirty state, without claiming semantic scope or runtime proof."""
    root = workspace.resolve()
    files = []
    for relative in sorted(set(references)):
        candidate = Path(relative)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise WorkflowError("source evidence paths must be workspace-relative")
        path = (root / candidate).resolve()
        if not path.is_relative_to(root):
            raise WorkflowError("source evidence escapes workspace")
        if path.is_file():
            files.append({"path": relative, "digest": hashlib.sha256(path.read_bytes()).hexdigest()})
        else:
            files.append({"path": relative, "digest": None})
    git = {}
    git_available = True
    for label, command in (("head", ["rev-parse", "HEAD"]),
                           ("status", ["status", "--porcelain=v1", "-z", "--untracked-files=all"]),
                           ("diff", ["diff", "--no-ext-diff", "--no-textconv", "HEAD", "--"])):
        try:
            result = subprocess.run(["git", "-C", str(root), *command], capture_output=True,
                                    timeout=10, env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
            if result.returncode:
                git_available = False
                break
            git[label] = hashlib.sha256(result.stdout).hexdigest()
        except (OSError, subprocess.TimeoutExpired):
            git_available = False
            break
    payload = {"workspace": str(root), "files": files, "git": git if git_available else None}
    return {"snapshot_digest": fingerprint(payload), "files": files,
            "coverage": "referenced-files-and-git-state" if git_available else "referenced-files-only",
            "complete": bool(files) and all(item["digest"] for item in files),
            "semantic_scope_verified": False}


def _record_fingerprint(manifest: dict[str, Any]) -> str:
    root = Path(manifest["record_root"])
    return fingerprint({relative: hashlib.sha256(context.resolve_beneath(root, Path(relative)).read_bytes()).hexdigest()
                        for relative in manifest["documents"]})


def _binding_fingerprint(args: argparse.Namespace, resolved: Any) -> str:
    paths = [resolved.project_dir / "project.yaml", Path(args.registry or context.platform_registry()).expanduser()]
    return fingerprint({"workspace": str(Path(args.workspace or os.getcwd()).resolve()),
                        "bindings": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
                                     for p in paths}})


def _compiler_fingerprint() -> str:
    return fingerprint({name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                        for name in ("intent_context.py", "context_session.py", "workflow_runtime.py")})


def prepare_workflow(args: argparse.Namespace, request: Any, *, session: SessionContext | None = None) -> dict[str, Any]:
    started = time.monotonic()
    request = validate_request(request, args.stage)
    if not request.get("records_required", True):
        if any(getattr(args, key, None) for key in ("goal", "now", "date", "updated", "artifacts", "focus",
                                                   "decision", "compare", "include_undated", "verify")):
            raise WorkflowError("record filters conflict with records_required=false")
        return {"schema": "workflow-plan/v1", "status": "prepared", "requested_operation": "answer",
                "mode": "answer", "stage": args.stage, "selection": {"status": "not-required", "documents": []},
                "document_readiness": None, "authorization": {"status": "NOT_REQUIRED", "action": None,
                    "reasons": [], "basis": [], "enforcement": "advisory"},
                "context": {"status": "not-required", "cache": "disabled", "required_expansions": []},
                "source_verification": "NOT_RUN", "next_action": "answer", "user_decision": None,
                "warnings": [], "metrics": {"parsed_document_count": 0, "gate_evaluation_count": 0}}
    args = argparse.Namespace(**vars(args))
    resolved = context.resolve_project(args)
    goal_resolution = {"method": "explicit-goal", "goal": args.goal}
    if not args.goal:
        if not request.get("query"):
            raise WorkflowError("provide --goal or query; unbounded record selection is not allowed")
        goal_resolution = context.resolve_goal_query(argparse.Namespace(**{**vars(args),
                                                       "query": request["query"], "stdin": False}))
        if goal_resolution["status"] != "resolved":
            return {"schema": "workflow-plan/v1", "status": goal_resolution["status"],
                    "selection": goal_resolution, "next_action": "clarify_goal",
                    "authorization": {"status": "BLOCKED", "reasons": ["GOAL_UNRESOLVED"]}}
        args.goal = goal_resolution["goal"]
    args.operation = request["requested_operation"]
    action = {"answer": "requirements", "plan": {"impact": "requirements", "requirements": "requirements",
               "design": "design", "tasks": "tasks"}.get(args.stage),
              "implement": "implement", "validate": "validate", "deploy": "deploy"}[request["requested_operation"]]
    workspace = Path(args.workspace or os.getcwd())
    parsed_count = hit_count = gate_count = 0
    for attempt in range(2):
        manifest = context.select(args)
        if manifest["project_id"] != resolved.project_id or Path(manifest["record_root"]).resolve() != resolved.root.resolve():
            raise WorkflowError("project identity changed during preparation")
        if manifest["status"] != "selected":
            return {"schema": "workflow-plan/v1", "status": manifest["status"], "selection": manifest,
                    "next_action": "clarify_goal", "authorization": {"status": "BLOCKED", "reasons": ["NO_MATCH"]}}
        before = _record_fingerprint(manifest)
        binding = _binding_fingerprint(args, resolved)
        rules = context.effective_rule_manifest(resolved.root, resolved.project_id,
                                               getattr(args, "environment_id", None), args.operation)
        runtime = DecisionRuntime(resolved.project_dir, resolved.project_id, args.goal)
        state_path = context.resolve_beneath(resolved.project_dir, Path("features") / args.goal / ".skip")
        snapshot = runtime.read_snapshot() if state_path.is_dir() else None
        gate_count += len(snapshot["gates"]) if snapshot else 0
        source = source_snapshot(workspace, request["scope"]["evidence_refs"])
        cache = DocumentCache(session, {"root": str(resolved.root.resolve()), "project": resolved.project_id,
                              "goal": args.goal, "binding": binding, "compiler": _compiler_fingerprint(),
                              "selection": manifest, "stage": args.stage, "rules": rules,
                              "environment": getattr(args, "environment_id", None), "operation": args.operation,
                              "filters": {k: getattr(args, k, None) for k in ("date", "updated", "now", "artifacts",
                                          "decision", "focus", "compare", "include_undated", "verify")},
                              "max_chars": args.max_chars})
        pack = context.context_pack(args, manifest=manifest, document_cache=cache, include_runtime=False)
        parsed_count += cache.parsed
        hit_count += cache.hits
        # Revalidate all ephemeral state. No source or authority result is read from cache.
        after_snapshot = runtime.read_snapshot() if state_path.is_dir() else None
        gate_count += len(after_snapshot["gates"]) if after_snapshot else 0
        stable = (before == _record_fingerprint(manifest) and manifest == context.select(args) and
                  binding == _binding_fingerprint(args, resolved) and snapshot == after_snapshot and
                  source == source_snapshot(workspace, request["scope"]["evidence_refs"]) and
                  rules == context.effective_rule_manifest(resolved.root, resolved.project_id,
                            getattr(args, "environment_id", None), args.operation))
        if stable:
            break
    else:
        return {"schema": "workflow-plan/v1", "status": "incomplete", "next_action": "stop",
                "selection": manifest, "authorization": {"status": "EVIDENCE_PENDING", "reasons": ["SOURCE_CHANGED"]}}
    if snapshot:
        authorization = {**snapshot["gates"][action], "basis": snapshot["basis"],
                         "ledger_head": snapshot["ledger_head"], "snapshot_token": snapshot["token"]}
    else:
        authorization = {"status": "BLOCKED", "action": action, "reasons": ["CAPABILITY_UNAVAILABLE"],
                         "basis": [], "enforcement": "advisory"}
    if request["requested_operation"] == "answer":
        authorization = {"status": "NOT_REQUIRED", "action": None, "reasons": [], "basis": [], "enforcement": "advisory"}
    evidence = request.get("source_evidence", {})
    source_status = ("CURRENT_SOURCE_ONLY" if source["complete"] and
                     evidence.get("snapshot_digest") == source["snapshot_digest"] else "EVIDENCE_PENDING")
    next_action = choose_next_action(request, pack, authorization, source_status)
    warnings = list(dict.fromkeys(list(resolved.warnings) + pack["warnings"] + cache.warnings))
    if request["requested_operation"] == "deploy":
        warnings.append("DEPLOY_DISPATCH_UNSUPPORTED: prepare does not execute deployment")
    result = {"schema": "workflow-plan/v1", "status": "prepared" if pack["status"] == "complete" else "incomplete",
              "requested_operation": request["requested_operation"], "mode": classify_depth(request),
              "stage": args.stage, "selection": manifest, "goal_resolution": goal_resolution,
              "document_readiness": pack["implementation_gate"], "authorization": authorization,
              "context": {"status": pack["status"], "cache": "enabled" if cache.enabled else "disabled",
                          "required_expansions": pack["required_expansions"]},
              "context_pack": pack, "source_verification": source_status, "source_snapshot": source,
              "next_action": next_action, "user_decision": (
                  {"kind": "approval", "action": action, "reasons": authorization["reasons"]}
                  if next_action == "request_approval" else None),
              "warnings": warnings, "metrics": {**pack["metrics"], "parsed_document_count": parsed_count,
                  "cache_hit_count": hit_count, "gate_evaluation_count": gate_count,
                  "snapshot_attempts": attempt + 1, "elapsed_ms": round((time.monotonic() - started) * 1000, 3)}}
    return result
