import json
import tempfile
import unittest
import subprocess
import sys
from pathlib import Path

from scripts.decision_runtime import DecisionRuntime, DecisionRuntimeError
from scripts.intent_context import ResolvedProject, goal_candidates


ARTIFACT = """---
schema: skip-artifact/v1
status: approved
implementation:
  gate: ready
---
# test
"""


class DecisionRuntimeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name) / "projects" / "p"
        self.goal_dir = self.project / "features" / "g"
        self.goal_dir.mkdir(parents=True)
        for name in ("impact", "prd", "system_design", "tasks"):
            (self.goal_dir / f"{name}.md").write_text(ARTIFACT, encoding="utf-8")
        self.runtime = DecisionRuntime(self.project, "p", "g")

    def tearDown(self):
        self.temp.cleanup()

    def command(self, operation="approve", action="implement", payload=None):
        state = self.runtime.replay()
        artifact = {"requirements": "prd", "design": "system_design", "tasks": "tasks"}.get(action)
        target_digest = self.runtime._artifact_state()[artifact]["digest"] if artifact else state["artifact_digest"]
        return {"schema": "skip-mutation/v1", "project_id": "p", "goal": "g",
                "operation": operation, "action": action,
                "target": {"kind": "artifact" if artifact else "goal", "id": artifact or "g", "digest": target_digest},
                "expected_digest": state["artifact_digest"], "payload": payload or {}}

    def test_legacy_goal_is_read_only_until_initialized(self):
        with self.assertRaisesRegex(DecisionRuntimeError, "legacy goal"):
            self.runtime.preview(self.command())
        with self.assertRaisesRegex(DecisionRuntimeError, "legacy goal"):
            self.runtime.inbox()
        self.assertFalse((self.goal_dir / ".skip").exists())
        result = self.runtime.initialize()
        self.assertEqual(result["status"], "initialized")

    def test_preview_is_deterministic_and_side_effect_free(self):
        self.runtime.initialize()
        before = sorted(str(path.relative_to(self.goal_dir)) for path in self.goal_dir.rglob("*"))
        first = self.runtime.preview(self.command())
        second = self.runtime.preview(self.command())
        after = sorted(str(path.relative_to(self.goal_dir)) for path in self.goal_dir.rglob("*"))
        self.assertEqual(first["request_id"], second["request_id"])
        self.assertEqual(before, after)

    def test_agent_cannot_approve_and_user_can(self):
        self.runtime.initialize()
        command = self.command()
        preview = self.runtime.preview(command)
        with self.assertRaisesRegex(DecisionRuntimeError, "user-originated"):
            self.runtime.allow(command, {"schema": "authority-envelope/v1", "kind": "agent_proposal", "request_id": preview["request_id"]})
        result = self.runtime.allow(command, {"schema": "authority-envelope/v1", "kind": "user_turn", "request_id": preview["request_id"]})
        self.assertEqual(result["status"], "COMMITTED")
        self.assertEqual(len(self.runtime.history()["events"]), 1)

    def test_stale_digest_fails_closed(self):
        self.runtime.initialize()
        command = self.command()
        (self.goal_dir / "tasks.md").write_text(ARTIFACT + "changed\n", encoding="utf-8")
        with self.assertRaisesRegex(DecisionRuntimeError, "changed"):
            self.runtime.preview(command)

    def test_artifact_change_makes_approval_and_downstream_gate_stale(self):
        self.runtime.initialize()
        for action in ("requirements", "design", "tasks"):
            command = self.command("approve", action)
            preview = self.runtime.preview(command)
            self.runtime.allow(command, {"schema": "authority-envelope/v1", "kind": "user_turn", "request_id": preview["request_id"]})
        self.assertEqual(self.runtime.evaluate_gate("implement")["status"], "ALLOW")
        (self.goal_dir / "prd.md").write_text(ARTIFACT + "semantic change\n", encoding="utf-8")
        gate = self.runtime.evaluate_gate("implement")
        self.assertEqual(gate["status"], "STALE")
        self.assertIn("REQUIREMENTS_APPROVAL_STALE", gate["reasons"])

    def test_revocation_changes_lifecycle(self):
        self.runtime.initialize()
        command = self.command("revoke", "implement")
        preview = self.runtime.preview(command)
        self.runtime.allow(command, {"schema": "authority-envelope/v1", "kind": "native_user_action", "request_id": preview["request_id"]})
        self.assertEqual(self.runtime.replay()["lifecycle"], "revoked")
        self.assertEqual(self.runtime.evaluate_gate("implement")["status"], "BLOCKED")
        resolved = ResolvedProject(Path(self.temp.name), "explicit", "p", self.project, "explicit-project", None, ())
        self.assertEqual(goal_candidates(resolved), [])

    def test_deploy_requires_fresh_validation_and_approval(self):
        self.runtime.initialize()
        self.assertIn("VALIDATION_EVIDENCE_MISSING", self.runtime.evaluate_gate("deploy")["reasons"])
        validation = self.command("record_validation", "validate", {"artifact_digest": self.runtime.replay()["artifact_digest"], "result": "pass"})
        pv = self.runtime.preview(validation)
        self.runtime.allow(validation, {"schema": "authority-envelope/v1", "kind": "user_turn", "request_id": pv["request_id"]})
        self.assertIn("REQUIREMENTS_APPROVAL_MISSING", self.runtime.evaluate_gate("deploy")["reasons"])
        for action in ("requirements", "design", "tasks"):
            approval = self.command("approve", action)
            preview = self.runtime.preview(approval)
            self.runtime.allow(approval, {"schema": "authority-envelope/v1", "kind": "user_turn", "request_id": preview["request_id"]})
        approval = self.command("approve", "deploy")
        pa = self.runtime.preview(approval)
        self.runtime.allow(approval, {"schema": "authority-envelope/v1", "kind": "user_turn", "request_id": pa["request_id"]})
        self.assertEqual(self.runtime.evaluate_gate("deploy")["status"], "ALLOW")

    def test_unknown_fields_and_path_escape_are_rejected(self):
        self.runtime.initialize()
        command = self.command()
        command["source_patch"] = "no"
        with self.assertRaises(DecisionRuntimeError):
            self.runtime.preview(command)
        with self.assertRaises(DecisionRuntimeError):
            DecisionRuntime(self.project, "p", "../escape").initialize()

    def test_inbox_projects_open_decision_summary_from_artifact(self):
        (self.goal_dir / "prd.md").write_text("""---
schema: skip-artifact/v1
status: draft-with-open-questions
implementation:
  gate: blocked
decisions:
  confirmed: []
  open: ["D-007"]
---
| ID | Date | Class | Decision | Why | Effect | Status |
|---|---|---|---|---|---|---|
| D-007 | today | PRODUCT | Keep receipts | Prevent drift | Reapproval | open |
""", encoding="utf-8")
        self.runtime.initialize()
        item = next(item for item in self.runtime.inbox()["items"] if item["id"] == "D-007")
        self.assertIn("Keep receipts", item["summary"])
        self.assertEqual(item["evidence"], "prd.md")

    def test_history_cli_emits_one_json_and_preserves_failure(self):
        (self.project / "project.yaml").write_text("project_id: p\ndisplay_name: Test\n", encoding="utf-8")
        command = [sys.executable, "scripts/intent_context.py", "history",
                   "--record-root", self.temp.name, "--project", "p", "--goal", "g"]

        def invoke():
            return subprocess.run(command, cwd=Path(__file__).parents[1],
                                  text=True, capture_output=True)

        missing = invoke()
        self.assertEqual(missing.returncode, 2, missing.stdout + missing.stderr)
        self.assertEqual(json.loads(missing.stdout)["status"], "error")

        self.runtime.initialize()
        for populated in (False, True):
            with self.subTest(populated=populated):
                if populated:
                    mutation = self.command()
                    preview = self.runtime.preview(mutation)
                    self.runtime.allow(mutation, {"schema": "authority-envelope/v1",
                                                 "kind": "user_turn", "request_id": preview["request_id"]})
                result = invoke()
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                value = json.loads(result.stdout)  # Rejects a second JSON/error response.
                self.assertEqual(value["status"], "ok")
                self.assertEqual(value["schema"], "decision-history/v1")
                self.assertEqual(value["project_id"], "p")
                self.assertEqual(value["goal"], "g")
                self.assertEqual(value["events"], self.runtime.history()["events"])
                self.assertEqual(bool(value["events"]), populated)
                self.assertEqual(result.stderr, "")

    def test_cli_round_trip_and_agent_authority_rejection(self):
        record_root = Path(self.temp.name)
        (self.project / "project.yaml").write_text("project_id: p\ndisplay_name: Test\n", encoding="utf-8")
        init = subprocess.run([sys.executable, "scripts/intent_context.py", "runtime-init",
                               "--record-root", str(record_root), "--project", "p", "--goal", "g"],
                              cwd=Path(__file__).parents[1], text=True, capture_output=True)
        self.assertEqual(init.returncode, 0, init.stdout + init.stderr)
        command = self.command()
        command_path = Path(self.temp.name) / "command.json"
        command_path.write_text(json.dumps(command), encoding="utf-8")
        preview = subprocess.run([sys.executable, "scripts/intent_context.py", "mutation",
                                  "--record-root", str(record_root), "--project", "p", "--goal", "g",
                                  "--command-file", str(command_path)], cwd=Path(__file__).parents[1],
                                 text=True, capture_output=True)
        self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
        request = json.loads(preview.stdout)["request_id"]
        denied = subprocess.run([sys.executable, "scripts/intent_context.py", "allow",
                                 "--record-root", str(record_root), "--project", "p", "--goal", "g",
                                 "--command-file", str(command_path), "--request-id", request,
                                 "--authority-kind", "agent_proposal"], cwd=Path(__file__).parents[1],
                                text=True, capture_output=True)
        self.assertEqual(json.loads(denied.stdout)["error_code"], "INVALID_AUTHORITY")


if __name__ == "__main__":
    unittest.main()
