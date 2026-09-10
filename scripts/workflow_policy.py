"""Pure procedure selection: never creates an approval."""
if not __package__:
    from goal_risk import POLICY_VERSION
else:
    from scripts.goal_risk import POLICY_VERSION


def evaluate_policy(operation, risk, open_decisions, *, force_full=False):
    reasons = list(risk.get("reasons", []))
    if operation == "answer":
        depth = "answer"
    elif risk.get("status") != "assessed":
        depth = "investigate"
    elif force_full or risk["affects"] or risk["reversibility"] != "easy":
        depth = "full"
        reasons.append("MATERIAL_FAILURE_COST" if not force_full else "FULL_REQUESTED")
    else:
        depth = "compact"
    return {"schema": "workflow-policy/v1", "policy_version": POLICY_VERSION,
            "workflow_depth": depth, "open_decisions": open_decisions, "reasons": reasons,
            "required_investigation": ["current_scope_and_impact"] if depth == "investigate" else [],
            "required_checks": ([] if depth == "answer" else
                                ["affected_behavior", "regression", *risk.get("affects", [])])}
