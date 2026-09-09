import copy
import json
import os
from pathlib import Path
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from scripts.context_session import DocumentCache, SessionContext
from scripts.test_workflow_runtime import WorkflowFixture
from scripts.workflow_runtime import prepare_workflow
from scripts import intent_context


class CacheTests(WorkflowFixture, unittest.TestCase):
    def session(self, identity="one"):
        directory = self.root / "cache"
        directory.mkdir(mode=0o700, exist_ok=True)
        return SessionContext(directory, identity, True)

    def prepare(self, session=None, args=None):
        return prepare_workflow(args or self.args(), self.current_request(), session=session or self.session())

    def test_warm_semantics_equal_and_zero_document_parses(self):
        self.approve_implementation()
        cold = self.prepare()
        warm = self.prepare()
        self.assertEqual(cold["context_pack"], warm["context_pack"])
        self.assertEqual(cold["authorization"], warm["authorization"])
        self.assertEqual(cold["metrics"]["parsed_document_count"], 4)
        self.assertEqual(warm["metrics"]["parsed_document_count"], 0)
        self.assertEqual(warm["metrics"]["cache_hit_count"], 4)
        self.assertGreater(warm["metrics"]["gate_evaluation_count"], 0)

    def test_changed_document_only_is_reparsed(self):
        self.prepare()
        path = self.goal / "prd.md"
        path.write_text(path.read_text() + "\nupdated\n")
        result = self.prepare()
        self.assertEqual(result["metrics"]["parsed_document_count"], 1)
        self.assertEqual(result["metrics"]["cache_hit_count"], 3)

    def test_new_and_removed_document_invalidate_selection(self):
        self.prepare()
        path = self.goal / "extra.md"
        path.write_text("# extra\n")
        self.assertEqual(self.prepare()["metrics"]["selected_document_count"], 5)
        path.unlink()
        self.assertEqual(self.prepare()["metrics"]["selected_document_count"], 4)

    def test_sessions_goals_and_rules_are_isolated(self):
        self.prepare()
        self.assertEqual(self.prepare(self.session("two"))["metrics"]["cache_hit_count"], 0)
        with patch.object(intent_context, "effective_rule_manifest", return_value={"changed": True}):
            self.assertEqual(self.prepare()["metrics"]["cache_hit_count"], 0)
        second = self.project / "features/second"
        second.mkdir()
        for path in self.goal.glob("*.md"):
            (second / path.name).write_bytes(path.read_bytes())
        args = self.args()
        args.goal = "second"
        self.assertEqual(self.prepare(args=args)["metrics"]["cache_hit_count"], 0)

    def test_binding_change_invalidates_cache(self):
        self.prepare()
        p = self.project / "project.yaml"
        p.write_text(p.read_text() + "display_name: changed\n")
        self.assertEqual(self.prepare()["metrics"]["cache_hit_count"], 0)

    def test_ledger_revocation_never_cached(self):
        self.approve_implementation()
        self.assertEqual(self.prepare()["next_action"], "implement")
        self.approve("implement", "revoke")
        warm = self.prepare()
        self.assertEqual(warm["metrics"]["parsed_document_count"], 0)
        self.assertEqual(warm["next_action"], "stop")
        self.assertEqual(warm["authorization"]["status"], "BLOCKED")
        for p in (self.root / "cache").glob("*.json"):
            data = json.loads(p.read_text())
            self.assertEqual(set(data), {"schema", "key", "fragments"})
            self.assertNotIn("action_gates", p.read_text())
            self.assertNotIn("ledger_head", p.read_text())
            self.assertEqual(p.stat().st_mode & 0o777, 0o600)

    def test_corrupt_cache_recovers_without_hiding_bad_original(self):
        self.prepare()
        for p in (self.root / "cache").glob("*.json"):
            p.write_text("{")
        result = self.prepare()
        self.assertEqual(result["metrics"]["parsed_document_count"], 4)
        self.assertIn("CACHE_READ_FAILED", result["warnings"])
        (self.goal / "prd.md").write_text("---\nproject_id: [invalid]\n---\n")
        with self.assertRaises(intent_context.SelectionError):
            self.prepare()

    def test_cached_original_read_error_is_not_recovered(self):
        session = self.session()
        cache = DocumentCache(session, {})
        path = self.goal / "prd.md"
        cache.read(path, "prd.md", intent_context.context_artifact)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            cache.read(path, "prd.md", intent_context.context_artifact)

    def test_cache_requires_host_cleanup_and_private_directory(self):
        session = self.session()
        disabled = SessionContext(session.cache_directory, "one", False)
        self.assertEqual(self.prepare(disabled)["context"]["cache"], "disabled")
        session.cache_directory.chmod(0o755)
        result = self.prepare(session)
        self.assertEqual(result["context"]["cache"], "disabled")
        self.assertIn("CACHE_UNAVAILABLE", result["warnings"])

    def test_symlink_root_and_cache_file_do_not_escape(self):
        session = self.session()
        link = self.root / "cache-link"
        link.symlink_to(session.cache_directory, target_is_directory=True)
        result = self.prepare(SessionContext(link, "one", True))
        self.assertEqual(result["context"]["cache"], "disabled")
        self.prepare(session)
        outside = self.root / "outside"
        outside.write_text("preserve")
        p = next(session.cache_directory.glob("*.json"))
        p.unlink()
        p.symlink_to(outside)
        self.prepare(session)
        self.assertEqual(outside.read_text(), "preserve")

    def test_write_failure_is_uncached_fallback(self):
        with patch.object(DocumentCache, "save_document_cache", side_effect=OSError("disk full")):
            result = self.prepare()
        self.assertEqual(result["status"], "prepared")
        self.assertIn("CACHE_WRITE_FAILED", result["warnings"])

    def test_legacy_context_output_unchanged_by_compiler_split(self):
        args = self.args()
        old = intent_context.context_pack(args)
        cached = self.prepare()["context_pack"]
        self.assertEqual(old, cached)

    def test_concurrent_writers_leave_valid_private_entries(self):
        session = self.session()
        def read(_):
            cache = DocumentCache(session, {"same": True})
            return cache.read(self.goal / "prd.md", "prd.md", intent_context.context_artifact)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(read, range(8)))
        self.assertTrue(all(item == results[0] for item in results))
        self.assertEqual(len(list(session.cache_directory.glob("*.json"))), 1)
        self.assertEqual(list(session.cache_directory.glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main()
