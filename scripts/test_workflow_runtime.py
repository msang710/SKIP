import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from scripts import intent_context
from scripts.decision_runtime import DecisionRuntime, DecisionRuntimeError
from scripts.workflow_runtime import WorkflowError, prepare_workflow, source_snapshot


class WorkflowFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "records/projects/p"
        self.goal = self.project / "features/g"
        self.goal.mkdir(parents=True)
        (self.project / "project.yaml").write_text("version: 1\nproject_id: p\n")
        for kind in ("impact", "prd", "system_design", "tasks"):
            (self.goal / f"{kind}.md").write_text(f'''---
schema: skip-artifact/v1
artifact: {kind}
id: g
project_id: p
status: approved
created: 2026-09-09
review:
  verdict: ready
implementation:
  gate: ready
decisions:
  confirmed: []
  open: []
---
# Example
## Goal
Continue the bounded work.
## Requirements
- Keep approvals current.
Review verdict: READY
Implementation gate: READY
''')
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "app.py").write_text("value = 1\n")
        self.runtime = DecisionRuntime(self.project, "p", "g")

    def args(self, stage="implementation", *extra):
        return intent_context.parser().parse_args(["prepare", "--record-root", str(self.root / "records"),
            "--project", "p", "--goal", "g", "--workspace", str(self.workspace),
            "--stage", stage, "--request-file", "-", *extra])

    def request(self, operation="implement"):
        return {"schema": "workflow-request/v1", "requested_operation": operation,
                "requested_depth": "auto", "scope": {"behavior_change": "no", "risk_flags": [],
                "evidence_refs": ["app.py"]}}

    def approve(self, action, operation="approve"):
        projection = self.runtime.replay()
        artifact = {"requirements": "prd", "design": "system_design", "tasks": "tasks"}.get(action)
        target_digest = (self.runtime._artifact_state()[artifact]["digest"] if artifact else projection["artifact_digest"])
        command = {"schema": "skip-mutation/v1", "project_id": "p", "goal": "g", "operation": operation,
                   "action": action, "target": {"kind": "artifact" if artifact else "goal", "id": artifact or "g",
                   "digest": target_digest}, "expected_digest": projection["artifact_digest"], "payload": {}}
        preview = self.runtime.preview(command)
        return self.runtime.allow(command, {"schema": "authority-envelope/v1", "kind": "user_turn",
                                            "request_id": preview["request_id"]})

    def approve_implementation(self):
        self.runtime.initialize()
        for action in ("requirements", "design", "tasks"):
            self.approve(action)

    def current_request(self, operation="implement"):
        request = self.request(operation)
        request["source_evidence"] = {"snapshot_digest": source_snapshot(self.workspace, ["app.py"])["snapshot_digest"]}
        return request


class WorkflowTests(WorkflowFixture, unittest.TestCase):
    def test_legacy_never_initializes_or_inherits_document_approval(self):
        before = sorted(str(p) for p in self.project.rglob("*"))
        result = prepare_workflow(self.args(), self.current_request())
        self.assertEqual(result["document_readiness"], "READY")
        self.assertEqual(result["authorization"]["status"], "BLOCKED")
        self.assertEqual(result["next_action"], "stop")
        self.assertEqual(before, sorted(str(p) for p in self.project.rglob("*")))

    def test_plan_does_not_turn_into_implementation(self):
        self.approve_implementation()
        result = prepare_workflow(self.args("design"), self.current_request("plan"))
        self.assertEqual(result["next_action"], "present_plan")

    def test_same_approval_reused_with_current_source(self):
        self.approve_implementation()
        request = self.current_request()
        first = prepare_workflow(self.args(), request)
        second = prepare_workflow(self.args(), request)
        self.assertEqual(second["next_action"], "implement")
        self.assertIsNone(second["user_decision"])
        self.assertEqual(first["authorization"], second["authorization"])
        self.assertTrue(second["authorization"]["basis"][0]["event_id"])

    def test_missing_then_stale_approval(self):
        self.runtime.initialize()
        result = prepare_workflow(self.args(), self.current_request())
        self.assertEqual(result["next_action"], "request_approval")
        self.assertIn("TASKS_APPROVAL_MISSING", result["user_decision"]["reasons"])
        for action in ("requirements", "design", "tasks"):
            self.approve(action)
        path = self.goal / "prd.md"
        path.write_text(path.read_text() + "changed\n")
        result = prepare_workflow(self.args(), self.current_request())
        self.assertEqual(result["authorization"]["status"], "STALE")
        self.assertEqual(result["next_action"], "revise_artifact")

    def test_compact_unknown_and_source_changes_require_inspection(self):
        self.approve_implementation()
        request = self.current_request()
        (self.workspace / "app.py").write_text("value = 2\n")
        self.assertEqual(prepare_workflow(self.args(), request)["next_action"], "inspect_source")
        request = self.current_request()
        request["requested_depth"] = "compact"
        request["scope"]["behavior_change"] = "unknown"
        result = prepare_workflow(self.args(), request)
        self.assertEqual(result["mode"], "full")
        self.assertEqual(result["next_action"], "inspect_source")

    def test_revocation_and_deploy_remain_separate(self):
        self.approve_implementation()
        result = prepare_workflow(self.args("validation"), self.current_request("deploy"))
        self.assertEqual(result["authorization"]["status"], "BLOCKED")
        self.assertIn("DEPLOY_APPROVAL_MISSING", result["authorization"]["reasons"])
        self.approve("implement", "revoke")
        self.assertEqual(prepare_workflow(self.args(), self.current_request())["next_action"], "stop")

    def test_no_match_and_ambiguous_never_widen(self):
        args = self.args()
        args.goal = "missing"
        result = prepare_workflow(args, self.request())
        self.assertEqual(result["status"], "no_match")
        self.assertEqual(result["selection"]["documents"], [])
        args.goal = None
        request = self.request()
        request["query"] = "bounded work"
        with patch.object(intent_context, "resolve_goal_query", return_value={"status": "ambiguous", "candidates": []}), \
                patch.object(intent_context, "select", side_effect=AssertionError("must not select")):
            self.assertEqual(prepare_workflow(args, request)["status"], "ambiguous")

    def test_invalid_options_and_path_escape(self):
        for args in (self.args("design"), self.args("implementation", "--now", "--date", "2026-09-09")):
            with self.assertRaises((WorkflowError, intent_context.SelectionError)):
                prepare_workflow(args, self.request())
        for path in ("../secret", "/etc/passwd"):
            request = self.request()
            request["scope"]["evidence_refs"] = [path]
            with self.assertRaises(WorkflowError):
                prepare_workflow(self.args(), request)

    def test_self_contained_answer_reads_nothing(self):
        request = self.request("answer")
        request["records_required"] = False
        args = self.args("restore")
        args.goal = None
        with patch.object(intent_context, "resolve_project", side_effect=AssertionError("must not resolve")):
            self.assertEqual(prepare_workflow(args, request)["next_action"], "answer")

    def test_changing_snapshot_is_bounded(self):
        with patch("scripts.workflow_runtime._record_fingerprint", side_effect=["a", "b", "c", "d"]):
            result = prepare_workflow(self.args(), self.request())
        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["authorization"]["reasons"], ["SOURCE_CHANGED"])

    def test_source_snapshot_tracks_git_dirty_and_deleted_references(self):
        def git(*args):
            subprocess.run(["git", "-C", str(self.workspace), *args], check=True, capture_output=True)
        git("init", "-q")
        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.invalid", "commit", "-qm", "baseline")
        before = source_snapshot(self.workspace, ["app.py"])
        (self.workspace / "new.txt").write_text("untracked")
        after = source_snapshot(self.workspace, ["app.py"])
        self.assertNotEqual(before["snapshot_digest"], after["snapshot_digest"])
        (self.workspace / "app.py").unlink()
        self.assertFalse(source_snapshot(self.workspace, ["app.py"])["complete"])

    def test_runtime_provenance_matches_gate_and_snapshot_retries(self):
        self.approve_implementation()
        snapshot = self.runtime.read_snapshot()
        self.assertEqual(snapshot["gates"]["implement"], self.runtime.evaluate_gate("implement"))
        for basis in snapshot["basis"]:
            self.assertEqual(basis["target"]["digest"], basis["current_digest"])
        original = self.runtime._artifact_state
        count = 0
        def changing():
            nonlocal count
            state = original()
            count += 1
            state["prd"]["digest"] = str(count)
            return state
        with patch.object(self.runtime, "_artifact_state", side_effect=changing):
            with self.assertRaisesRegex(DecisionRuntimeError, "changed during snapshot"):
                self.runtime.read_snapshot()
        self.assertEqual(count, 4)

    def test_cli_and_help(self):
        command = [sys.executable, "scripts/intent_context.py"]
        for subcommand in ("prepare", "report"):
            result = subprocess.run(command + [subcommand, "--help"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
        args = self.args("design")
        result = subprocess.run(command + ["prepare", "--project", "p", "--record-root", args.record_root,
            "--goal", "g", "--workspace", str(self.workspace), "--stage", "design", "--request-file", "-"],
            input=json.dumps(self.request("plan")), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(json.loads(result.stdout)["next_action"], "present_plan")

    def test_agent_fields_cannot_supply_authorization_or_session(self):
        for field in ("authorization", "authority_kind", "session_id", "cache_directory"):
            request = self.request()
            request[field] = "user_turn"
            with self.assertRaises(WorkflowError):
                prepare_workflow(self.args(), request)

    def test_record_read_failure_and_invalid_ledger_are_not_masked(self):
        self.approve_implementation()
        event = next((self.goal / ".skip/ledger").glob("*.yaml"))
        event.write_text("{")
        with self.assertRaises(DecisionRuntimeError) as failure:
            prepare_workflow(self.args(), self.request())
        self.assertEqual(failure.exception.error_code, "RECOVERY_REQUIRED")

    def test_missing_source_reference_stays_pending_even_with_allow(self):
        self.approve_implementation()
        request = self.current_request()
        request["scope"]["evidence_refs"] = []
        result = prepare_workflow(self.args(), request)
        self.assertEqual(result["source_verification"], "EVIDENCE_PENDING")
        self.assertEqual(result["next_action"], "inspect_source")


if __name__ == "__main__":
    unittest.main()
