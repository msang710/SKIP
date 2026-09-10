"""Small shared entry surface for native adapters and source installations.

Read-only preparation is the default. Activation is a separate host user action.
The module never implements, deploys, or records test success on the agent's behalf.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import sys
if not __package__:
    import intent_context as context
    from host_context import EntryError, HostContext, UserEvent, beneath, digest, text
    from goal_risk import assess, snapshot, string_list
    from goal_resolution import resolve_goal
    from project_bootstrap import preview, apply, atomic_write, locked, revision
    from workflow_policy import evaluate_policy
    from workflow_authorization import authorize, revalidate
else:
    from scripts import intent_context as context
    from scripts.host_context import EntryError, HostContext, UserEvent, beneath, digest, text
    from scripts.goal_risk import assess, snapshot, string_list
    from scripts.goal_resolution import resolve_goal
    from scripts.project_bootstrap import preview, apply, atomic_write, locked, revision
    from scripts.workflow_policy import evaluate_policy
    from scripts.workflow_authorization import authorize, revalidate


def validate_request(request):
    required = {"schema", "request_id", "text", "operation", "scope", "open_decisions"}
    optional = {"goal", "goal_risk", "change_risk", "force_full"}
    if not isinstance(request, dict) or set(request) - required - optional or required - set(request):
        raise EntryError("invalid entry request fields; authority is supplied separately by the host")
    if request["schema"] != "workflow-request/v2" or not isinstance(request["operation"], str) or request["operation"] not in {"answer", "plan", "implement", "validate", "deploy"}:
        raise EntryError("unsupported request contract or operation")
    text(request["request_id"], "request id", 200)
    text(request["text"], "request text")
    if "goal" in request:
        text(request["goal"], "goal", 200)
    if type(request.get("force_full", False)) is not bool:
        raise EntryError("force_full must be boolean")
    string_list(request["open_decisions"], "open decisions")
    scope = request["scope"]
    if not isinstance(scope, dict) or set(scope) != {"paths", "summary"}:
        raise EntryError("scope requires paths and summary")
    string_list(scope["paths"], "scope paths")
    text(scope["summary"], "scope summary")
    if len(set(scope["paths"])) != len(scope["paths"]):
        raise EntryError("duplicate scope paths")
    return request


def identity_args(host, root, registry, project_id, paseo_project_id=None):
    return argparse.Namespace(record_root=str(root), registry=str(registry), project=project_id,
                              workspace=str(host.workspace), paseo_project_id=paseo_project_id)


def status_view(plan):
    goal, gate, policy = plan.get("goal", {}), plan.get("authorization", {}), plan.get("policy", {})
    decisions = policy.get("open_decisions", [])
    action = plan["next_action"]
    messages = {"inspect_source": "변경 범위와 위험을 조사합니다.", "implement": "요청한 범위의 구현을 시작할 수 있습니다.",
                "present_plan": "계획을 검토합니다.", "clarify_goal": "작업할 목표를 확인해야 합니다.",
                "activate": "이 프로젝트에서 SKIP을 활성화할 수 있습니다.", "request_approval": "진행에 필요한 결정을 확인합니다.",
                "stop": "진행 조건을 확인해야 합니다.", "answer": "요청에 답합니다.", "verify": "검증을 진행합니다."}
    return {"schema": "status-view/v1", "goal": goal.get("goal"), "outcome": messages.get(action, action),
            "decision_needed": decisions, "recommendation": None,
            "risk_summary": plan.get("risk", {}).get("affects", []), "checks": [],
            "gaps": list(dict.fromkeys(plan.get("gaps", []) + gate.get("reasons", []))),
            "next_action": action, "detail_refs": ["authorization", "policy", "risk", "source_snapshot"]}


def prepare(host, root, registry, request=None, *, event=None, project_id=None, paseo_project_id=None, receipt=None):
    if request is not None:
        request = validate_request(request)
        if request["operation"] == "answer" and not request.get("goal"):
            result = {"schema": "workflow-plan/v2", "status": "prepared", "next_action": "answer",
                      "creates_goals": False, "records_required": False}
            return {**result, "view": status_view(result)}
    binding = preview(host, root, registry, paseo_project_id=paseo_project_id)
    if project_id:
        context.safe_slug(project_id, "project")
        if binding["status"] != "resolved" or binding["project_id"] != project_id:
            raise EntryError("explicit project conflicts with observed workspace binding")
    if request is None:
        result = {"schema": "workflow-plan/v2", "status": "prepared", "bootstrap": binding,
                  "next_action": "activate" if binding["status"] == "preview" else "answer", "creates_goals": False}
        return {**result, "view": status_view(result)}
    request = validate_request(request)
    source = snapshot(host.workspace, request["scope"]["paths"])
    if binding["status"] != "resolved":
        result = {"schema": "workflow-plan/v2", "status": "project_missing", "bootstrap": binding,
                  "source_snapshot": source, "next_action": "activate", "creates_goals": False}
        return {**result, "view": status_view(result)}
    args = identity_args(host, root, registry, binding["project_id"], paseo_project_id)
    goal = resolve_goal(args, host, request, event)
    if goal["status"] != "resolved":
        result = {"schema": "workflow-plan/v2", "status": goal["status"], "goal": goal,
                  "source_snapshot": source, "next_action": "answer" if request["operation"] == "answer" else "clarify_goal"}
        return {**result, "view": status_view(result)}
    risk = {"status": "unknown", "reasons": ["MISSING_RISK_EVIDENCE"], "affects": []}
    if "goal_risk" in request and "change_risk" in request:
        risk = assess(request["goal_risk"], request["change_risk"], source, request["scope"])
    decisions = sorted(set(request["open_decisions"] + goal["open_decisions"]))
    policy = evaluate_policy(request["operation"], risk, decisions,
                             force_full=request.get("force_full", False) or goal["has_artifacts"])
    gate = authorize(host, event, request, goal, policy, risk, source, full_gate=goal.get("full_gate"))
    if receipt is not None:
        gate = revalidate(receipt, gate)
    if request["operation"] == "deploy":
        action = "stop"
    elif goal["lifecycle"] != "active" or goal["hold"]:
        action = "stop"
    elif request["operation"] == "answer":
        action = "answer"
    elif policy["workflow_depth"] == "investigate" or gate["status"] == "STALE":
        action = "inspect_source"
    elif decisions:
        action = "request_approval"
    elif request["operation"] == "plan":
        action = "present_plan"
    elif request["operation"] == "validate":
        action = "verify"
    else:
        action = "implement" if gate["status"] == "ALLOW" else "request_approval"
    result = {"schema": "workflow-plan/v2", "status": "prepared", "project_id": binding["project_id"],
              "goal": goal, "risk": risk, "policy": policy, "authorization": gate,
              "source_snapshot": source, "next_action": action, "creates_goals": False,
              "gaps": ["DEPLOY_DISPATCH_UNSUPPORTED"] if request["operation"] == "deploy" else []}
    return {**result, "view": status_view(result)}


def record_current(host, root, project_id, goal, current, facts, checks, *, expected_revision=None, source_id=None):
    """Persist measured current facts only; caller evidence remains attributed.

    This API is called by a host adapter within its NOW-write activation. It does
    not accept plans, approvals, lifecycle changes, or arbitrary output paths.
    """
    context.safe_slug(project_id, "project")
    context.safe_slug(goal, "goal")
    if current != snapshot(host.workspace, [item["path"] for item in current["files"]]):
        raise EntryError("current source changed before NOW recording")
    string_list(facts, "current facts")
    if not facts or not current["files"]:
        raise EntryError("NOW requires observed facts and source evidence")
    if not __package__:
        from workflow_report import EVIDENCE_STATUSES, SURFACES
    else:
        from scripts.workflow_report import EVIDENCE_STATUSES, SURFACES
    if not isinstance(checks, list):
        raise EntryError("invalid checks")
    for check in checks:
        if not isinstance(check, dict) or set(check) - {"surface", "status", "reference", "summary"} or not {"surface", "status"} <= set(check):
            raise EntryError("invalid check")
        if check["status"] not in EVIDENCE_STATUSES or check["surface"] not in SURFACES:
            raise EntryError("invalid evidence status or surface")
        if check["status"] == "PASS" and not check.get("reference"):
            raise EntryError("PASS requires evidence reference")
    project = beneath(Path(root), "projects/" + project_id)
    if not (project / "project.yaml").is_file() or (project / ".bootstrap-pending").exists():
        raise EntryError("project is not active")
    metadata = context.scalar_yaml(project / "project.yaml")
    sources = metadata.get("sources", {})
    if source_id is None and len(sources) == 1:
        source_id = next(iter(sources))
    if source_id not in sources:
        raise EntryError("select the verified source_id for this project's NOW record")
    source_root = sources[source_id].get("source_root", ".")
    context.safe_slug(source_id, "source id")
    beneath(host.workspace, source_root)
    path = beneath(project, f"NOW/goals/{goal}.md")
    with locked(beneath(Path(root), f".control/now/{project_id}.lock")):
        if revision(path) != expected_revision:
            raise EntryError("NOW changed; read and merge before retry")
        import datetime
        value = ("---\nkind: now\nproject_id: " + project_id + "\nid: " + goal + "\nscope: " + goal +
                 "\nstatus: partially-verified\nverified_revision: unversioned\nverified_at: " + datetime.date.today().isoformat() +
                 "\nsource_id: " + source_id + "\nsource_root: " + source_root + "\n---\n\n# 현재 확인된 상태\n\n## 현재 사실\n\n" +
                 "\n".join("- " + fact.replace("\n", " ") for fact in facts) +
                 "\n\n## 근거\n\n에이전트가 제공한 검증 결과이며 Core가 테스트를 실행한 결과는 아닙니다.\n\n```json\n" +
                 json.dumps({"source": current, "checks": checks}, ensure_ascii=False, indent=2) + "\n```\n")
        atomic_write(path, value.encode())
    return {"status": "recorded", "path": str(path), "revision": revision(path)}


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--record-root")
    parser.add_argument("--registry")
    parser.add_argument("--project")
    parser.add_argument("--paseo-project-id")
    parser.add_argument("--request-file", help="read-only v2 request, '-' for stdin; never establishes user origin")
    parser.add_argument("--interactive", action="store_true", help="receive the actual user's new request at the terminal")
    parser.add_argument("--activate", action="store_true", help="interactive project activation, separate from a work request")
    args = parser.parse_args(argv)
    try:
        host = HostContext.local(args.workspace)
        root = Path(args.record_root or os.environ.get("INTENT_TO_CODE_RECORD_ROOT") or context.platform_data_root())
        registry = Path(args.registry or os.environ.get("INTENT_TO_CODE_WORKSPACE_REGISTRY") or context.platform_registry())
        request, event = None, None
        if args.request_file:
            raw = sys.stdin.read() if args.request_file == "-" else Path(args.request_file).read_text(encoding="utf-8")
            request = json.loads(raw)
        if args.interactive or args.activate:
            if not sys.stdin.isatty() or args.request_file:
                raise EntryError("native terminal input required; request JSON cannot supply authority")
            import uuid
            host = HostContext.local(args.workspace, session_id=str(uuid.uuid4()))
            if args.activate:
                print("이 프로젝트를 SKIP에 연결합니다. 계속하려면 yes를 입력하세요: ", end="", file=sys.stderr, flush=True)
                if input().strip() != "yes":
                    raise EntryError("activation cancelled")
                event = UserEvent.from_native_action(host, str(uuid.uuid4()), "activate", "activate")
                result = apply(host, event, preview(host, root, registry, paseo_project_id=args.paseo_project_id))
                print(json.dumps(result, ensure_ascii=False))
                return 0
            print("구현할 요청: ", end="", file=sys.stderr, flush=True)
            user_text = input()
            request = {"schema": "workflow-request/v2", "request_id": str(uuid.uuid4()), "text": user_text,
                       "operation": "implement", "scope": {"paths": [], "summary": user_text}, "open_decisions": []}
            event = UserEvent.from_native_action(host, request["request_id"], user_text, "implement")
        result = prepare(host, root, registry, request, event=event, project_id=args.project, paseo_project_id=args.paseo_project_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "prepared" else 2
    except (EntryError, context.SelectionError, OSError, ValueError) as exc:
        print(json.dumps({"schema": "entry-error/v1", "status": "error", "error": str(exc)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
