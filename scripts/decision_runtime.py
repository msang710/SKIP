#!/usr/bin/env python3
"""Goal-scoped decision, approval, lifecycle, and deploy gates for SKIP."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    from decision_runtime_store import RuntimeStore, StoreError, canonical_bytes
except ModuleNotFoundError:
    from scripts.decision_runtime_store import RuntimeStore, StoreError, canonical_bytes


ACTIONS = {"requirements", "design", "tasks", "implement", "validate", "deploy"}
LIFECYCLES = {"active", "completed", "revoked", "superseded"}
AUTHORITY_KINDS = {"user_turn", "interactive_cli", "native_user_action"}
MUTATIONS = {"approve", "revoke", "supersede", "complete", "record_validation", "record_deploy"}


class DecisionRuntimeError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.error_code = code
        self.retryable = retryable


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def request_id(command: dict[str, Any]) -> str:
    identity = {
        "schema": command.get("schema"), "project_id": command.get("project_id"),
        "goal": command.get("goal"), "operation": command.get("operation"),
        "action": command.get("action"), "target": command.get("target"),
        "expected_digest": command.get("expected_digest"), "payload": command.get("payload", {}),
    }
    return digest(identity)[:24]


@dataclass(frozen=True)
class GoalRuntimePaths:
    project_dir: Path
    goal: str

    @property
    def goal_dir(self) -> Path:
        base = (self.project_dir / "features").resolve()
        candidate = (base / self.goal).resolve()
        try:
            candidate.relative_to(base)
        except ValueError as exc:
            raise DecisionRuntimeError("INVALID_TRANSITION", "goal escapes project features") from exc
        return candidate

    @property
    def state_dir(self) -> Path:
        return self.goal_dir / ".skip"


class DecisionRuntime:
    def __init__(self, project_dir: Path, project_id: str, goal: str) -> None:
        self.project_id = project_id
        self.goal = goal
        self.paths = GoalRuntimePaths(project_dir, goal)
        self.store = RuntimeStore(self.paths.state_dir)

    def initialize(self) -> dict[str, Any]:
        if not self.paths.goal_dir.is_dir():
            raise DecisionRuntimeError("INVALID_TRANSITION", "goal directory does not exist")
        self.store.initialize()
        projection = self.replay()
        self.store.recover(projection)
        return {"schema": "goal-runtime-init/v1", "operation": "initialize", "status": "initialized",
                "project_id": self.project_id, "goal": self.goal,
                "artifact_digest": projection["artifact_digest"]}

    def require_initialized(self) -> None:
        if not self.paths.state_dir.is_dir():
            raise DecisionRuntimeError("CAPABILITY_UNAVAILABLE", "legacy goal has no initialized decision runtime")

    def _artifact_state(self) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for name in ("impact", "prd", "system_design", "tasks"):
            path = self.paths.goal_dir / f"{name}.md"
            if not path.exists():
                continue
            raw = path.read_bytes()
            text = raw.decode("utf-8")
            status = None
            gate = None
            confirmed: list[str] = []
            open_decisions: list[str] = []
            decision_details: dict[str, str] = {}
            if text.startswith("---\n"):
                header = text.split("---\n", 2)[1]
                for line in header.splitlines():
                    if line.startswith("status:"):
                        status = line.split(":", 1)[1].strip()
                    if line.strip().startswith("gate:"):
                        gate = line.split(":", 1)[1].strip()
                    stripped = line.strip()
                    if stripped.startswith(("confirmed:", "open:")):
                        key, encoded = stripped.split(":", 1)
                        try:
                            values = json.loads(encoded.strip())
                        except json.JSONDecodeError:
                            values = []
                        if isinstance(values, list) and all(isinstance(value, str) for value in values):
                            if key == "confirmed": confirmed = values
                            else: open_decisions = values
            for line in text.splitlines():
                cells = [cell.strip() for cell in line.strip().strip("|").split("|")] if line.strip().startswith("|") else []
                if cells and cells[0] in open_decisions:
                    decision_details[cells[0]] = " | ".join(cells[1:-1])[:2000]
            result[name] = {"digest": hashlib.sha256(raw).hexdigest(), "status": status, "gate": gate,
                            "confirmed_decisions": confirmed, "open_decisions": open_decisions,
                            "decision_details": decision_details}
        return result

    def replay(self) -> dict[str, Any]:
        return self._replay_events(self._read_events(), self._artifact_state())

    def _read_events(self) -> list[dict[str, Any]]:
        try:
            return self.store.events()
        except StoreError as exc:
            raise DecisionRuntimeError(exc.code, str(exc)) from exc

    def _replay_events(self, events: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
        projection: dict[str, Any] = {
            "schema": "goal-projection/v1", "project_id": self.project_id, "goal": self.goal,
            "lifecycle": "active", "approvals": {}, "validation": None, "deployments": [],
            "pending": {}, "head": None, "sequence": 0,
        }
        for event in events:
            projection["sequence"] = event["sequence"]
            projection["head"] = event["event_id"]
            operation = event["event_type"]
            action = event.get("action")
            if operation == "approve":
                projection["approvals"][action] = event["target"]
                projection["pending"].pop(event["authority"]["request_id"], None)
            elif operation == "record_validation":
                projection["validation"] = event["payload"]
            elif operation == "record_deploy":
                projection["deployments"].append(event["payload"])
            elif operation in {"revoke", "supersede", "complete"}:
                projection["lifecycle"] = {"revoke": "revoked", "supersede": "superseded", "complete": "completed"}[operation]
        projection["artifact_digest"] = digest(state)
        return projection

    def evaluate_gate(self, action: str) -> dict[str, Any]:
        self.require_initialized()
        if action not in ACTIONS:
            raise DecisionRuntimeError("INVALID_TRANSITION", f"unknown action: {action}")
        state = self._artifact_state()
        projection = self.replay()
        return self._evaluate_gate(action, state, projection)

    def _evaluate_gate(self, action: str, state: dict[str, Any], projection: dict[str, Any]) -> dict[str, Any]:
        reasons: list[str] = []
        required = {
            "requirements": ["impact"], "design": ["prd"], "tasks": ["system_design"],
            "implement": ["prd", "system_design", "tasks"], "validate": ["tasks"],
            "deploy": ["prd", "system_design", "tasks"],
        }[action]
        for artifact in required:
            item = state.get(artifact)
            if not item:
                reasons.append(f"MISSING_{artifact.upper()}")
            elif action in {"implement", "validate", "deploy"} and item.get("gate") != "ready":
                reasons.append(f"{artifact.upper()}_NOT_READY")
        if action in {"design", "tasks", "implement", "deploy"}:
            if any(item.get("open_decisions") for item in state.values()):
                reasons.append("OPEN_PRODUCT_DECISIONS")
        if projection["lifecycle"] != "active" and action not in {"validate"}:
            reasons.append("GOAL_NOT_ACTIVE")
        prerequisite_approvals = {
            "requirements": [], "design": ["requirements"], "tasks": ["design"],
            "implement": ["requirements", "design", "tasks"], "validate": ["implement"],
            "deploy": ["requirements", "design", "tasks", "deploy"],
        }[action]
        stale: list[str] = []
        for approval_action in prerequisite_approvals:
            receipt = projection["approvals"].get(approval_action)
            if not receipt:
                reasons.append(f"{approval_action.upper()}_APPROVAL_MISSING")
                continue
            current_digest = self._target_digest(approval_action, state, projection["artifact_digest"])
            if receipt.get("digest") != current_digest:
                stale.append(f"{approval_action.upper()}_APPROVAL_STALE")
        if stale:
            return self._gate(action, "STALE", stale)
        if action == "deploy":
            if not projection.get("validation"):
                reasons.append("VALIDATION_EVIDENCE_MISSING")
            elif projection["validation"].get("artifact_digest") != projection["artifact_digest"]:
                return self._gate(action, "STALE", ["VALIDATION_EVIDENCE_STALE"])
        return self._gate(action, "BLOCKED" if reasons else "ALLOW", reasons)

    def read_snapshot(self) -> dict[str, Any]:
        """Read-only consistent gates and provenance; retry a changing snapshot once."""
        self.require_initialized()
        for _ in range(2):
            state = self._artifact_state()
            events = self._read_events()
            projection = self._replay_events(events, state)
            latest = {event["action"]: event for event in events if event["event_type"] == "approve"}
            basis = [{"action": action, "event_id": event["event_id"], "target": event["target"],
                      "current_digest": self._target_digest(action, state, projection["artifact_digest"])}
                     for action, event in sorted(latest.items())]
            token = digest({"artifacts": state, "events": events})
            if token == digest({"artifacts": self._artifact_state(), "events": self._read_events()}):
                return {"token": token, "ledger_head": projection["head"],
                        "lifecycle": projection["lifecycle"], "basis": basis,
                        "gates": {action: self._evaluate_gate(action, state, projection)
                                  for action in sorted(ACTIONS)}}
        raise DecisionRuntimeError("SOURCE_CHANGED", "runtime changed during snapshot", retryable=True)

    def _target_digest(self, action: str, state: dict[str, Any], artifact_digest: str) -> str:
        artifact = {"requirements": "prd", "design": "system_design", "tasks": "tasks"}.get(action)
        return state.get(artifact, {}).get("digest", "") if artifact else artifact_digest

    def _gate(self, action: str, status: str, reasons: list[str]) -> dict[str, Any]:
        return {"schema": "gate-evaluation/v1", "operation": "gate", "status": status,
                "reason_code": reasons[0] if reasons else None, "reasons": reasons,
                "project_id": self.project_id, "goal": self.goal, "action": action,
                "enforcement": "advisory", "next_actions": [] if not reasons else ["resolve_gate_reasons"]}

    def parse_command(self, command: dict[str, Any]) -> dict[str, Any]:
        allowed = {"schema", "project_id", "goal", "operation", "action", "target", "expected_digest", "payload"}
        if set(command) - allowed or command.get("schema") != "skip-mutation/v1":
            raise DecisionRuntimeError("INVALID_TRANSITION", "invalid mutation schema or unknown field")
        if command.get("project_id") != self.project_id or command.get("goal") != self.goal:
            raise DecisionRuntimeError("INVALID_TRANSITION", "mutation identity mismatch")
        if command.get("operation") not in MUTATIONS or command.get("action") not in ACTIONS:
            raise DecisionRuntimeError("INVALID_TRANSITION", "unknown mutation operation or action")
        target = command.get("target")
        if not isinstance(target, dict) or set(target) != {"kind", "id", "digest"}:
            raise DecisionRuntimeError("INVALID_TRANSITION", "target must contain kind, id, and digest")
        if not isinstance(command.get("payload", {}), dict):
            raise DecisionRuntimeError("INVALID_TRANSITION", "payload must be an object")
        operation = command["operation"]
        payload = command.get("payload", {})
        if operation == "supersede" and not payload.get("replacement_goal"):
            raise DecisionRuntimeError("INVALID_TRANSITION", "supersede requires replacement_goal")
        if operation == "record_validation" and not all(key in payload for key in ("artifact_digest", "result")):
            raise DecisionRuntimeError("INVALID_TRANSITION", "validation receipt requires artifact_digest and result")
        if operation == "record_deploy" and not all(key in payload for key in ("target", "impact", "rollout", "rollback")):
            raise DecisionRuntimeError("DEPLOY_BLOCKED", "deploy receipt requires target, impact, rollout, and rollback")
        return command

    def preview(self, command: dict[str, Any]) -> dict[str, Any]:
        self.require_initialized()
        command = self.parse_command(command)
        current = self.replay()
        expected = command.get("expected_digest")
        if expected != current["artifact_digest"]:
            raise DecisionRuntimeError("STALE_DIGEST", "mutation target changed since it was proposed")
        # Artifact approvals bind both the whole goal snapshot and the exact artifact.
        target_digest = self._target_digest(command["action"], self._artifact_state(), current["artifact_digest"])
        if command["target"]["digest"] != target_digest:
            raise DecisionRuntimeError("STALE_DIGEST", "target digest does not match current target")
        if command["operation"] == "record_deploy" and self.evaluate_gate("deploy")["status"] != "ALLOW":
            raise DecisionRuntimeError("DEPLOY_BLOCKED", "deploy gate is not ALLOW")
        rid = request_id(command)
        return {"schema": "mutation-preview/v1", "operation": "preview", "status": "PENDING",
                "request_id": rid, "project_id": self.project_id, "goal": self.goal,
                "action": command["action"], "command": command,
                "caller": f"$skip --allow {rid}", "current_digest": current["artifact_digest"],
                "gate": self.evaluate_gate(command["action"])}

    def allow(self, command: dict[str, Any], authority: dict[str, Any]) -> dict[str, Any]:
        self.require_initialized()
        preview = self.preview(command)
        if authority.get("schema") != "authority-envelope/v1" or authority.get("kind") not in AUTHORITY_KINDS:
            raise DecisionRuntimeError("INVALID_AUTHORITY", "approval lacks user-originated authority")
        if authority.get("request_id") != preview["request_id"]:
            raise DecisionRuntimeError("INVALID_AUTHORITY", "authority request does not match preview")
        with self.store.lock():
            current = self.replay()
            if command["expected_digest"] != current["artifact_digest"]:
                raise DecisionRuntimeError("STALE_DIGEST", "mutation became stale before commit")
            sequence = int(current["sequence"]) + 1
            event_base = {
                "schema": "goal-ledger-event/v1", "sequence": sequence,
                "occurred_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "project_id": self.project_id, "goal": self.goal,
                "event_type": command["operation"], "action": command["action"],
                "target": command["target"],
                "authority": {"kind": authority["kind"], "request_id": preview["request_id"], "host": authority.get("host")},
                "payload": command.get("payload", {}), "previous_event_id": current["head"],
            }
            event = dict(event_base, event_id=digest(event_base)[:24])
            projected = self._project_with(current, event)
            try:
                self.store.commit(event, projected)
            except StoreError as exc:
                raise DecisionRuntimeError(exc.code, str(exc)) from exc
        return {"schema": "mutation-result/v1", "operation": "allow", "status": "COMMITTED",
                "request_id": preview["request_id"], "project_id": self.project_id,
                "goal": self.goal, "action": command["action"], "event_id": event["event_id"],
                "receipt": {"target": command["target"], "authority": event["authority"]}}

    def _project_with(self, current: dict[str, Any], event: dict[str, Any]) -> dict[str, Any]:
        # Reuse replay semantics without trusting the projection as authority.
        result = json.loads(json.dumps(current))
        result["sequence"], result["head"] = event["sequence"], event["event_id"]
        operation, action = event["event_type"], event["action"]
        if operation == "approve": result["approvals"][action] = event["target"]
        elif operation == "record_validation": result["validation"] = event["payload"]
        elif operation == "record_deploy": result["deployments"].append(event["payload"])
        elif operation in {"revoke", "supersede", "complete"}:
            result["lifecycle"] = {"revoke": "revoked", "supersede": "superseded", "complete": "completed"}[operation]
        return result

    def inbox(self) -> dict[str, Any]:
        self.require_initialized()
        projection = self.replay()
        items = []
        for artifact, state in self._artifact_state().items():
            for decision_id in state.get("open_decisions", []):
                items.append({"id": decision_id, "kind": "decision", "status": "OPEN",
                              "reasons": ["PRODUCT_DECISION_REQUIRED"],
                              "summary": state.get("decision_details", {}).get(decision_id),
                              "evidence": f"{artifact}.md", "digest": state["digest"]})
        for action in ACTIONS:
            gate = self.evaluate_gate(action)
            if gate["status"] != "ALLOW":
                items.append({"id": f"gate:{action}", "kind": "gate", "action": action,
                              "status": gate["status"], "reasons": gate["reasons"]})
        return {"schema": "decision-inbox/v1", "operation": "inbox", "status": "ok",
                "project_id": self.project_id, "goal": self.goal,
                "lifecycle": projection["lifecycle"], "items": items}

    def history(self, limit: int = 50) -> dict[str, Any]:
        self.require_initialized()
        events = self.store.events()[-max(1, min(limit, 200)):]
        return {"schema": "decision-history/v1", "project_id": self.project_id,
                "goal": self.goal, "events": events}
