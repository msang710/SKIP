"""Evidence-bound risk inputs. These validate consistency, not domain semantics."""
from __future__ import annotations
if not __package__:
    from host_context import EntryError, beneath, digest, text
else:
    from scripts.host_context import EntryError, beneath, digest, text

POLICY_VERSION = "failure-cost/1"
DIMENSIONS = {"business_rules", "inventory", "money", "permissions", "sensitive_data",
              "persisted_data", "external_state", "boot_recovery"}


def string_list(value, name):
    if not isinstance(value, list) or len(value) > 128:
        raise EntryError(f"invalid {name}")
    for item in value:
        text(item, name, 4096)
    return value


def snapshot(workspace, paths):
    """Bounded current file evidence; Git and a whole-repo scan are unnecessary."""
    files = []
    for relative in sorted(set(string_list(paths, "paths"))):
        path = beneath(workspace, relative)
        if path.is_file():
            import hashlib
            if path.stat().st_size > 8 * 1024 * 1024:
                raise EntryError("evidence file exceeds 8 MiB; choose a bounded reference")
            value = hashlib.sha256(path.read_bytes()).hexdigest()
        elif not path.exists():
            value = None  # Non-existence is measured evidence for a new file.
        else:
            raise EntryError("evidence reference must identify a file")
        files.append({"path": relative, "digest": value})
    return {"digest": digest({"workspace": str(workspace.resolve()), "files": files}),
            "files": files, "coverage": "referenced-files-only", "semantic_scope_verified": False}


def assess(goal, change, current, scope):
    if not isinstance(goal, dict) or set(goal) != {"schema", "revision", "affects", "failure_impact", "reversibility", "uncertainty", "evidence"}:
        raise EntryError("invalid goal-risk/v1 fields")
    if goal["schema"] != "goal-risk/v1" or type(goal["revision"]) is not int or goal["revision"] < 1:
        raise EntryError("invalid goal risk revision")
    fields = {"schema", "goal_revision", "source_digest", "scope_digest", "policy_version", "affects",
              "reversibility", "uncertainty", "evidence", "exclusions"}
    if not isinstance(change, dict) or set(change) != fields or change["schema"] != "change-risk/v1":
        raise EntryError("invalid change-risk/v1 fields")
    for risk in (goal, change):
        if set(string_list(risk["affects"], "affects")) - DIMENSIONS:
            raise EntryError("unknown impact dimension")
        if not isinstance(risk["reversibility"], str) or risk["reversibility"] not in {"easy", "requires_reconciliation", "difficult", "unknown"}:
            raise EntryError("invalid reversibility")
        if not isinstance(risk["uncertainty"], str) or risk["uncertainty"] not in {"low", "high", "unknown"}:
            raise EntryError("invalid uncertainty")
        string_list(risk["evidence"], "risk evidence")
    text(goal["failure_impact"], "failure impact")
    exclusions = change["exclusions"]
    if not isinstance(exclusions, dict) or set(exclusions) - set(goal["affects"]):
        raise EntryError("invalid risk exclusions")
    for reason in exclusions.values():
        text(reason, "exclusion evidence")
    covered = {item["path"] for item in current["files"]}
    refs = set(goal["evidence"] + change["evidence"] + list(exclusions.values()))
    reasons = []
    if (change["source_digest"] != current["digest"] or change["scope_digest"] != digest(scope) or
            change["policy_version"] != POLICY_VERSION or change["goal_revision"] != goal["revision"]):
        reasons.append("STALE_RISK")
    if not goal["evidence"] or not change["evidence"] or not refs <= covered:
        reasons.append("MISSING_RISK_EVIDENCE")
    if any(r["uncertainty"] != "low" or r["reversibility"] == "unknown" for r in (goal, change)):
        reasons.append("UNKNOWN_IMPACT")
    if set(exclusions) & set(change["affects"]):
        raise EntryError("excluded dimension is affected by change")
    dimensions = sorted((set(goal["affects"]) - set(exclusions)) | set(change["affects"]))
    return {"schema": "risk-assessment/v1", "status": "unknown" if reasons else "assessed",
            "affects": dimensions, "reversibility": change["reversibility"], "reasons": reasons,
            "digest": digest({"goal": goal, "change": change}),
            "goal": goal, "change": change, "semantic_scope_verified": False}
