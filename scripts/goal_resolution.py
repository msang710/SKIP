"""Request-only new goals; existing record selection stays in the canonical resolver."""
from __future__ import annotations
import argparse
if not __package__:
    import intent_context as context
    from host_context import EntryError, beneath, digest
    from decision_runtime import DecisionRuntime
else:
    from scripts import intent_context as context
    from scripts.host_context import EntryError, beneath, digest
    from scripts.decision_runtime import DecisionRuntime


def resolve_goal(args, host, request, event):
    resolved = context.resolve_project(args)
    if request.get("goal"):
        slug = context.safe_slug(request["goal"], "goal")
        feature = beneath(resolved.project_dir, "features/" + slug)
        now = beneath(resolved.project_dir, "NOW/goals/" + slug + ".md")
        if not feature.is_dir() and not now.is_file():
            raise EntryError("explicit goal does not exist; do not invent a historical goal")
        selection = {"status": "resolved", "goal": slug, "method": "explicit-goal"}
    else:
        query_args = argparse.Namespace(**{**vars(args), "query": request["text"], "stdin": False})
        selection = context.resolve_goal_query(query_args)
    if selection["status"] == "ambiguous":
        return selection
    if selection["status"] == "no_match":
        if request["operation"] not in {"plan", "implement"} or event is None or not event.matches(host, request):
            return {"status": "no_match", "reason": "CURRENT_USER_WORK_REQUEST_REQUIRED", "creates_goals": False}
        slug = "request-" + digest({"project": resolved.project_id, "host": host.binding(),
                                   "request_id": request["request_id"], "text": request["text"]})[:20]
        # Session-only: no files are created by goal resolution.
        return {"status": "resolved", "goal": slug, "method": "current-user-request", "lifecycle": "active",
                "hold": False, "open_decisions": [], "has_artifacts": False, "record_basis": [],
                "request_id": request["request_id"], "persistent": False}
    slug = selection["goal"]
    feature = beneath(resolved.project_dir, "features/" + slug)
    runtime = beneath(feature, ".skip")
    lifecycle, full_gate, record_basis, decisions, hold = "active", None, [], [], False
    if runtime.is_dir():
        measured = DecisionRuntime(resolved.project_dir, resolved.project_id, slug).read_snapshot()
        lifecycle, full_gate = measured["lifecycle"], measured["gates"]["implement"]
        record_basis.append(measured["token"])
    documents = [beneath(feature, name) for name in context.GOAL_ROUTING_ARTIFACTS]
    documents.append(beneath(resolved.project_dir, f"NOW/goals/{slug}.md"))
    for path in documents:
        if not path.is_file():
            continue
        metadata = context.frontmatter(path)
        if metadata.get("project_id", resolved.project_id) != resolved.project_id or metadata.get("id", slug) != slug:
            raise EntryError("goal record identity mismatch")
        import hashlib
        record_basis.append(hashlib.sha256(path.read_bytes()).hexdigest())
        decision_state = metadata.get("decisions", {})
        if not isinstance(decision_state, dict):
            raise EntryError("goal decision state requires structured metadata")
        values = decision_state.get("open", [])
        if not isinstance(values, list) or not all(isinstance(item, str) for item in values):
            raise EntryError("invalid open decisions")
        decisions.extend(values)
        hold = hold or metadata.get("status") in {"hold", "blocked", "revoked", "superseded"}
    return {"status": "resolved", "goal": slug, "method": selection.get("method"),
            "lifecycle": lifecycle, "hold": hold, "open_decisions": sorted(set(decisions)),
            "has_artifacts": feature.is_dir(), "record_basis": record_basis,
            "full_gate": full_gate, "persistent": True}
