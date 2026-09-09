"""Evidence-preserving workflow reports. This module never executes validation."""

from __future__ import annotations

from copy import deepcopy
import json
from typing import Any


class WorkflowError(ValueError):
    error_code = "INVALID_REQUEST"


EVIDENCE_STATUSES = {"PASS", "FAIL", "NOT_RUN", "EVIDENCE_PENDING", "STALE", "BLOCKED"}
SURFACES = {"source", "test", "build", "package", "install", "runtime", "gui", "device", "production"}
AUTH_STATUSES = {"ALLOW", "BLOCKED", "STALE", "EVIDENCE_PENDING", "NOT_REQUIRED"}


def string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise WorkflowError(f"{label} must be a nonempty string")
    return value


def strings(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise WorkflowError(f"{label} must be a list of nonempty strings")
    return value


def validate_result(value: Any) -> dict[str, Any]:
    allowed = {"schema", "requested_outcome", "outcome_status", "changes", "evidence",
               "authorization", "gaps", "next_decision", "selection", "document_readiness", "metrics"}
    required = {"schema", "requested_outcome", "outcome_status", "changes", "evidence",
                "authorization", "gaps", "next_decision"}
    if not isinstance(value, dict) or set(value) - allowed or required - set(value):
        raise WorkflowError("invalid workflow result fields")
    result = deepcopy(value)
    if result["schema"] != "workflow-result/v1":
        raise WorkflowError("expected workflow-result/v1; prepare is not completion evidence")
    string(result["requested_outcome"], "requested_outcome")
    if not isinstance(result["outcome_status"], str) or result["outcome_status"] not in {"complete", "partial", "blocked", "not_run"}:
        raise WorkflowError("invalid outcome_status")
    strings(result["changes"], "changes")
    strings(result["gaps"], "gaps")
    if result["next_decision"] is not None:
        string(result["next_decision"], "next_decision")
    auth = result["authorization"]
    if not isinstance(auth, dict) or not isinstance(auth.get("status"), str) or auth["status"] not in AUTH_STATUSES:
        raise WorkflowError("invalid authorization status")
    strings(auth.get("reasons", []), "authorization.reasons")
    evidence = result["evidence"]
    if not isinstance(evidence, list):
        raise WorkflowError("evidence must be a list")
    for item in evidence:
        if not isinstance(item, dict) or set(item) - {"surface", "status", "reference", "summary"}:
            raise WorkflowError("invalid evidence fields")
        if (not isinstance(item.get("surface"), str) or item["surface"] not in SURFACES or
                not isinstance(item.get("status"), str) or item["status"] not in EVIDENCE_STATUSES):
            raise WorkflowError("invalid evidence surface/status")
        if item.get("reference") is not None:
            string(item["reference"], "evidence.reference")
        if item.get("summary") is not None:
            string(item["summary"], "evidence.summary")
        if item["status"] == "PASS" and not item.get("reference"):
            item["status"] = "EVIDENCE_PENDING"
            result["gaps"].append(f"{item['surface']}: PASS has no evidence reference")
    if not evidence:
        result["gaps"].append("EVIDENCE_PENDING: no execution or observation evidence supplied")
    result["gaps"] = list(dict.fromkeys(result["gaps"]))
    if result["outcome_status"] == "complete" and (
        not evidence or any(x["status"] != "PASS" for x in evidence) or result["gaps"]
    ):
        result["outcome_status"] = "partial"
    return result


def build_summary(value: Any) -> dict[str, Any]:
    result = validate_result(value)
    checks = [f"{x['surface']}: {x['status']}" +
              (f" — {x['reference']}" if x.get("reference") else "") +
              (f" ({x['summary']})" if x.get("summary") else "") for x in result["evidence"]]
    if not checks:
        checks = ["EVIDENCE_PENDING"]
    remaining = list(result["gaps"])
    auth = result["authorization"]
    if auth["status"] not in {"ALLOW", "NOT_REQUIRED"}:
        remaining.append(f"{auth.get('action', 'authorization')}: {auth['status']}")
        remaining.extend(auth.get("reasons", []))
    if result.get("document_readiness"):
        checks.append(f"문서 준비: {result['document_readiness']}; 실행 권한: {auth['status']}")
    selection = result.get("selection")
    if isinstance(selection, dict):
        if selection.get("status") in {"ambiguous", "no_match", "error"}:
            remaining.append(f"선택: {selection['status']}")
        remaining.extend(strings(selection.get("warnings", []), "selection.warnings"))
    if result["next_decision"]:
        remaining.append(result["next_decision"])
    return {"result": f"{result['requested_outcome']} — {result['outcome_status']}",
            "changes": result["changes"], "checks": checks,
            "remaining": list(dict.fromkeys(remaining)), "detail": result}


def render_brief(value: Any) -> str:
    summary = build_summary(value)
    lines = [f"결과: {summary['result']}"]
    if summary["changes"]:
        lines.append("변경: " + "; ".join(summary["changes"]))
    lines.append("확인: " + "; ".join(summary["checks"]))
    lines.append("남은 일: " + ("; ".join(summary["remaining"]) or "없음"))
    return "\n".join(lines) + "\n"


def render_detail(value: Any) -> str:
    result = validate_result(value)
    return render_brief(result) + "\n" + json.dumps(result, ensure_ascii=False, indent=2) + "\n"
