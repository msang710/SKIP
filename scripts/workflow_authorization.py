"""Independent v2 advisory gate; v1 full-artifact gates retain their meaning."""
if not __package__:
    from host_context import digest
else:
    from scripts.host_context import digest


def authorize(host, event, request, goal, policy, risk, source, *, full_gate=None):
    reasons = []
    basis = None
    if goal.get("lifecycle") != "active":
        reasons.append("GOAL_NOT_ACTIVE")
    if goal.get("hold"):
        reasons.append("GOAL_ON_HOLD")
    if policy["open_decisions"]:
        reasons.append("OPEN_PRODUCT_DECISIONS")
    if request["operation"] != "implement":
        reasons.append("IMPLEMENT_NOT_REQUESTED")
    if event is None or not event.matches(host, request):
        reasons.append("AUTHORITY_UNAVAILABLE")
    if policy["workflow_depth"] == "compact":
        basis = "scoped_user_request"
    elif policy["workflow_depth"] == "full":
        basis = "full_artifact_approval"
        if not full_gate or full_gate.get("status") != "ALLOW":
            reasons.extend((full_gate or {}).get("reasons", ["FULL_APPROVAL_REQUIRED"]))
    else:
        reasons.append("INVESTIGATION_REQUIRED")
    binding = {"host": host.binding(), "request": request, "goal": goal, "policy": policy,
               "risk_digest": risk.get("digest"), "source_digest": source["digest"], "full_gate": full_gate}
    return {"schema": "execution-gate/v2", "status": "BLOCKED" if reasons else "ALLOW",
            "action": "implement", "execution_basis": basis, "enforcement": "advisory",
            "origin_verification": "host-adapter-assertion" if event else "unavailable",
            "reasons": list(dict.fromkeys(reasons)), "scope_digest": digest(request["scope"]),
            "binding_digest": digest(binding)}


def revalidate(receipt, current_gate):
    if not isinstance(receipt, dict) or receipt.get("schema") != "execution-gate/v2":
        return {**current_gate, "status": "BLOCKED", "reasons": ["UNSUPPORTED_RECEIPT_CONTRACT"]}
    if receipt.get("status") != "ALLOW":
        return current_gate
    if receipt.get("scope_digest") != current_gate["scope_digest"]:
        return {**current_gate, "status": "BLOCKED", "reasons": ["REQUEST_SCOPE_CHANGED"]}
    if current_gate["status"] != "ALLOW":
        return current_gate
    if receipt != current_gate:
        return {**current_gate, "status": "STALE", "reasons": ["EXECUTION_BINDING_CHANGED"]}
    return current_gate
