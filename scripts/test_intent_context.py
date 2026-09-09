#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from scripts import intent_context
from scripts.skip_cli import menu_move, toggled_disabled, verbatim_project_rule
from scripts.skip_setup import DEFAULT_CORE_RULES, RulePaths, SetupService


SCRIPT = Path(__file__).with_name("intent_context.py")


class SelectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.project = self.root / "projects" / "example-project"
        (self.project / "features" / "alpha").mkdir(parents=True)
        (self.project / "NOW" / "goals").mkdir(parents=True)
        self.write("project.yaml", "version: 1\nproject_id: example-project\n")
        self.write("NOW/index.md", """---\nkind: now\nproject_id: example-project\nscope: index\nstatus: current\nverified_revision: abc\nverified_at: 2026-08-25\nsource_root: .\n---\n# Index\n""")
        self.write("NOW/goals/alpha.md", """---\nkind: now\nproject_id: example-project\nscope: alpha\nstatus: current\nverified_revision: abc\nverified_at: 2026-08-25\nsource_root: .\n---\n# Alpha\n## Product behavior in force\nD-003 is live.\n""")
        self.write("NOW/system.md", """---\nkind: now\nproject_id: example-project\nscope: system\nstatus: current\nverified_revision: abc\nverified_at: 2026-08-25\nsource_root: .\n---\n# System\n""")
        self.write("NOW/validation.md", """---\nkind: now\nproject_id: example-project\nscope: validation\nstatus: current\nverified_revision: abc\nverified_at: 2026-08-25\nsource_root: .\n---\n# Validation\n""")
        self.write("features/alpha/prd.md", """---\nid: alpha\nproject_id: example-project\ncreated: 2026-08-25\nupdated: 2026-08-26\n---\n# PRD\nD-003\n## Goal\nShip alpha safely.\n## Product decisions\n| ID | Decision | Status |\n|---|---|---|\n| D-003 | Preserve blocked gates. | approved |\n## Requirements\n- The pack preserves the implementation gate.\n## Open questions\n- Runtime validation remains EVIDENCE_PENDING.\nReview verdict: READY - requirements approved\nImplementation gate: BLOCKED - runtime evidence missing\n""")
        self.write("features/alpha/tasks.md", """---\nid: alpha\nproject_id: example-project\ncreated: 2026-08-24\nupdated: 2026-08-25\n---\n# Tasks\n""")
        self.write("features/alpha/undated.md", "# Legacy\n")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write(self, relative: str, content: str) -> None:
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def run_select(self, *args: str) -> tuple[int, dict]:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "select", "--record-root", str(self.root), "--project", "example-project", *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return proc.returncode, json.loads(proc.stdout)

    def run_resolve(self, *args: str) -> tuple[int, dict]:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "resolve",
                "--record-root",
                str(self.root),
                "--project",
                "example-project",
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return proc.returncode, json.loads(proc.stdout)

    def run_context(self, *args: str) -> tuple[int, dict]:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "context",
                "--record-root",
                str(self.root),
                "--project",
                "example-project",
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return proc.returncode, json.loads(proc.stdout)

    def run_goals(self, *args: str, stdin: str | None = None) -> tuple[int, dict]:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "goals",
                "--record-root",
                str(self.root),
                "--project",
                "example-project",
                *args,
            ],
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return proc.returncode, json.loads(proc.stdout)

    def run_setup(self, *args: str) -> tuple[int, dict]:
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "setup",
                "--record-root",
                str(self.root),
                "--project",
                "example-project",
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return proc.returncode, json.loads(proc.stdout)

    def repository_script(self, root: Path) -> Path:
        script = root / "scripts" / "intent_context.py"
        script.parent.mkdir(parents=True)
        shutil.copy2(SCRIPT, script)
        shutil.copy2(SCRIPT.with_name("skip_setup.py"), script.with_name("skip_setup.py"))
        return script

    def run_repository_select(
        self,
        repository: Path,
        project_id: str,
        environment: dict[str, str] | None = None,
    ) -> tuple[int, dict]:
        clean_environment = os.environ.copy()
        clean_environment.pop("INTENT_TO_CODE_RECORD_ROOT", None)
        if environment:
            clean_environment.update(environment)
        proc = subprocess.run(
            [sys.executable, str(self.repository_script(repository)), "select", "--project", project_id, "--now"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=clean_environment,
        )
        return proc.returncode, json.loads(proc.stdout)

    def test_platform_default_ignores_repository_local_records(self) -> None:
        repository = self.root / "skill-repository"
        bundled = repository / "records" / "projects" / "bundled-project"
        (bundled / "NOW").mkdir(parents=True)
        (bundled / "project.yaml").write_text("version: 2\nproject_id: bundled-project\n", encoding="utf-8")
        platform = self.root / "platform-data" / "SKIP"
        project = platform / "projects" / "platform-project"
        (project / "NOW").mkdir(parents=True)
        (project / "project.yaml").write_text("version: 2\nproject_id: platform-project\n", encoding="utf-8")
        (project / "NOW" / "index.md").write_text("# Platform\n", encoding="utf-8")
        code, data = self.run_repository_select(
            repository,
            "platform-project",
            {"XDG_DATA_HOME": str(self.root / "platform-data")},
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["record_root"], str(platform.resolve()))
        self.assertEqual(data["record_root_source"], "platform-default")

    def test_environment_root_precedes_repository_root(self) -> None:
        repository = self.root / "skill-repository"
        bundled = repository / "records" / "projects" / "bundled-project"
        bundled.mkdir(parents=True)
        environment_root = self.root / "environment-records"
        project = environment_root / "projects" / "environment-project"
        (project / "NOW").mkdir(parents=True)
        (project / "project.yaml").write_text("version: 2\nproject_id: environment-project\n", encoding="utf-8")
        (project / "NOW" / "index.md").write_text("# Environment\n", encoding="utf-8")
        code, data = self.run_repository_select(
            repository,
            "environment-project",
            {"INTENT_TO_CODE_RECORD_ROOT": str(environment_root)},
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["record_root_source"], "environment")

    def test_help_succeeds_without_project_or_record_store(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "select", "--help", "--now"],
            cwd=str(self.root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(proc.stderr, "")
        self.assertIn("show this help message and exit", proc.stdout)
        self.assertIn("--now", proc.stdout)
        self.assertIn("--compare", proc.stdout)
        self.assertIn("--paseo-project-id", proc.stdout)

    def test_context_help_succeeds_without_project_or_record_store(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "context", "--help"],
            cwd=str(self.root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--stage", proc.stdout)
        self.assertIn("--max-chars", proc.stdout)

    def test_goals_help_succeeds_without_project_or_record_store(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "goals", "--help"],
            cwd=str(self.root),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("--query", proc.stdout)
        self.assertIn("--stdin", proc.stdout)

    def test_goal_resolver_exact_slug_is_deterministic(self) -> None:
        first_code, first = self.run_goals("--query", "continue alpha implementation")
        second_code, second = self.run_goals("--query", "continue alpha implementation")
        self.assertEqual(first_code, 0)
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], "goal-resolution/v1")
        self.assertEqual(first["goal"], "alpha")
        self.assertEqual(first["method"], "exact-slug")
        self.assertEqual(first["candidates"][0]["evidence"], ["projects/example-project/features/alpha/prd.md"])

    def test_goal_resolver_uses_stdin_without_echoing_query(self) -> None:
        query = "Ship alpha safely without repeating the private request"
        code, data = self.run_goals("--stdin", stdin=query)
        self.assertEqual(code, 0)
        self.assertEqual(data["goal"], "alpha")
        self.assertNotIn(query, json.dumps(data))

    def test_goal_resolver_normalizes_korean_particles_on_english_terms(self) -> None:
        self.write("features/context-pack-efficiency/prd.md", """---\nid: context-pack-efficiency\nproject_id: example-project\ntitle: Context Pack token efficiency requirements\n---\n# PRD\n## Goal\nReduce Context Pack input efficiently.\n""")
        code, data = self.run_goals("--query", "Context Pack의 토큰 효율을 개선하자")
        self.assertEqual(code, 0)
        self.assertEqual(data["goal"], "context-pack-efficiency")
        self.assertEqual(data["method"], "unique-terms")

    def test_goal_resolver_ambiguous_and_no_match_fail_closed(self) -> None:
        self.write("features/beta/prd.md", """---\nid: beta\nproject_id: example-project\ntitle: Beta release tracking\n---\n# PRD\n## Goal\nTrack beta releases safely.\n""")
        self.write("features/gamma/prd.md", """---\nid: gamma\nproject_id: example-project\ntitle: Gamma release tracking\n---\n# PRD\n## Goal\nTrack gamma releases safely.\n""")
        code, data = self.run_goals("--query", "release tracking")
        self.assertEqual(code, 2)
        self.assertEqual(data["status"], "ambiguous")
        self.assertIsNone(data["goal"])
        self.assertEqual([item["slug"] for item in data["candidates"]], ["beta", "gamma"])
        code, data = self.run_goals("--query", "unrelated telescope calibration")
        self.assertEqual(code, 3)
        self.assertEqual(data["status"], "no_match")
        self.assertEqual(data["candidates"], [])

    def test_goal_resolver_result_hands_off_to_canonical_selector(self) -> None:
        code, resolution = self.run_goals("--query", "alpha")
        self.assertEqual(code, 0)
        code, selection = self.run_select("--goal", resolution["goal"], "--artifacts", "prd")
        self.assertEqual(code, 0)
        self.assertEqual(selection["documents"], ["projects/example-project/features/alpha/prd.md"])

    def test_goal_resolver_rejects_symlinked_goal_directory(self) -> None:
        outside = self.root / "outside-goal"
        outside.mkdir()
        (self.project / "features" / "linked-goal").symlink_to(outside, target_is_directory=True)
        code, data = self.run_goals("--query", "alpha")
        self.assertEqual(code, 2)
        self.assertIn("must not be a symlink", data["error"])

    def test_goal_resolver_rejects_malformed_or_conflicting_metadata(self) -> None:
        self.write("features/broken/prd.md", "---\nid: broken\nproject_id: example-project\n")
        code, data = self.run_goals("--query", "alpha")
        self.assertEqual(code, 2)
        self.assertIn("unterminated frontmatter", data["error"])
        self.write("features/broken/prd.md", "---\nid: another-goal\nproject_id: example-project\n---\n# PRD\n")
        code, data = self.run_goals("--query", "alpha")
        self.assertEqual(code, 2)
        self.assertIn("id mismatch", data["error"])

    def test_context_pack_is_deterministic_and_preserves_blocked_gate(self) -> None:
        args = ("--goal", "alpha", "--artifacts", "prd", "--stage", "implementation")
        first_code, first = self.run_context(*args)
        second_code, second = self.run_context(*args)
        self.assertEqual(first_code, 0)
        self.assertEqual(second_code, 0)
        self.assertEqual(first, second)
        self.assertEqual(first["schema"], "context-pack/v1")
        self.assertEqual(first["selection"]["goal"], "alpha")
        self.assertEqual(first["review_verdict"], "READY")
        self.assertEqual(first["implementation_gate"], "BLOCKED")
        self.assertEqual(first["open_items"][0]["path"], "projects/example-project/features/alpha/prd.md")

    def test_structured_frontmatter_is_authoritative_across_translated_headings(self) -> None:
        self.write("features/alpha/prd.md", """---
schema: skip-artifact/v1
artifact: prd
id: alpha
project_id: example-project
status: approved
review:
  verdict: ready
  purpose: requirements-approval
implementation:
  gate: blocked
  reason: tasks-not-approved
decisions:
  confirmed: ["D-003"]
  open: []
created: 2026-08-25
updated: 2026-08-29
---
# 요구사항
## 임의로 번역한 결정 제목
| 상태 | 설명 | ID |
|---|---|---|
| 확정 | 보존 | D-003 |
Review verdict: READY
Implementation gate: BLOCKED
""")
        code, data = self.run_context("--goal", "alpha", "--artifacts", "prd", "--stage", "implementation")
        self.assertEqual(code, 0)
        self.assertEqual(data["confirmed_decisions"][0]["text"], "D-003")
        self.assertEqual(data["artifacts"][0]["metadata_source"], "structured")

    def test_structured_frontmatter_conflict_fails_closed(self) -> None:
        self.write("features/alpha/prd.md", """---
schema: skip-artifact/v1
artifact: prd
id: alpha
project_id: example-project
status: draft
review:
  verdict: ready
implementation:
  gate: blocked
decisions:
  confirmed: []
  open: []
---
# PRD
Review verdict: NEEDS_WORK
Implementation gate: BLOCKED
""")
        code, data = self.run_context("--goal", "alpha", "--artifacts", "prd", "--stage", "requirements")
        self.assertEqual(code, 2)
        self.assertIn("conflicts", data["error"])

    def test_malformed_structured_frontmatter_fails_closed(self) -> None:
        self.write("features/alpha/prd.md", """---
schema: skip-artifact/v1
artifact: prd
id: alpha
project_id: example-project
status: impossible
review:
  verdict: ready
implementation:
  gate: blocked
---
# PRD
""")
        code, data = self.run_context("--goal", "alpha", "--artifacts", "prd", "--stage", "requirements")
        self.assertEqual(code, 2)
        self.assertIn("invalid structured artifact status", data["error"])

    def test_structured_decision_filter_uses_metadata(self) -> None:
        self.write("features/alpha/prd.md", """---
schema: skip-artifact/v1
artifact: prd
id: alpha
project_id: example-project
status: approved
review:
  verdict: ready
implementation:
  gate: blocked
decisions:
  confirmed: ["D-900"]
  open: []
---
# PRD without decision text
Review verdict: READY
Implementation gate: BLOCKED
""")
        code, data = self.run_select("--goal", "alpha", "--decision", "D-900")
        self.assertEqual(code, 0)
        self.assertIn("projects/example-project/features/alpha/prd.md", data["documents"])

    def test_setup_preview_does_not_write(self) -> None:
        code, data = self.run_setup("--disable", "C-010")
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "preview")
        self.assertTrue(data["changes"]["core"])
        self.assertFalse((self.root / "config" / "core-rules.yaml").exists())

    def test_shared_setup_service_preserves_canonical_core_text_and_verbatim_project_rule(self) -> None:
        service = SetupService(
            RulePaths(
                self.root / "config" / "core-rules.yaml",
                self.project / "project-rules.yaml",
            ),
            "example-project",
            lambda value, _label: value,
        )
        current = service.load()
        core, project = json.loads(json.dumps(current))
        core["disabled_default_rule_ids"] = toggled_disabled([], "C-010")
        original = "이 프로젝트는 PostgreSQL 안정 버전을 사용한다.\n예외는 사용자가 직접 결정한다."
        project["rules"].append(verbatim_project_rule("postgres-stable", original, changed_at="2026-08-29"))
        changes = service.apply(current, (core, project))
        self.assertEqual(changes, {"core": True, "project": True})
        loaded_core, loaded_project = service.load()
        self.assertEqual(loaded_core["disabled_default_rule_ids"], ["C-010"])
        self.assertEqual(loaded_project["rules"][0]["rule"], original)
        self.assertEqual(DEFAULT_CORE_RULES["C-010"], "Do not implicitly alter unrelated user work or records.")

    def test_tui_reducer_wraps_and_toggles_without_changing_other_ids(self) -> None:
        import curses

        self.assertEqual(menu_move(0, curses.KEY_UP, 3), 2)
        self.assertEqual(menu_move(2, curses.KEY_DOWN, 3), 0)
        self.assertEqual(toggled_disabled(["C-001"], "C-002"), ["C-001", "C-002"])
        self.assertEqual(toggled_disabled(["C-001", "C-002"], "C-001"), ["C-002"])

    def test_skip_adapter_preserves_natural_language_without_classifying_subcommands(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(SCRIPT.with_name("skip_cli.py")), "지금 보는", "tasks.md를 검토해줘"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertEqual(
            json.loads(proc.stdout),
            {"schema": "skip.invoke/v1", "text": "지금 보는 tasks.md를 검토해줘"},
        )

    def test_setup_apply_writes_validated_rules_and_context_selects_them(self) -> None:
        project_rule = json.dumps(
            {
                "id": "latest-stable",
                "rule": "Use the latest stable dependency when compatible.",
                "scope": {"kind": "project"},
                "status": "active",
                "authority": {"changed_at": "2026-08-29"},
            }
        )
        code, data = self.run_setup("--disable", "C-010", "--project-rule", project_rule, "--apply")
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "applied")
        self.assertTrue((self.root / "config" / "core-rules.yaml").exists())
        code, pack = self.run_context("--goal", "alpha", "--artifacts", "prd", "--stage", "requirements")
        self.assertEqual(code, 0)
        self.assertNotIn("C-010", pack["effective_rules"]["default_core_rule_ids"])
        self.assertEqual(pack["effective_rules"]["project_rules"][0]["id"], "latest-stable")

    def test_environment_rule_is_withheld_without_exact_scope_match(self) -> None:
        project_rule = json.dumps(
            {
                "id": "shell-restart",
                "rule": "Use the approved restart command.",
                "command": "safe-restart",
                "scope": {
                    "kind": "environment-operation",
                    "environment_id": "machine-a",
                    "operation": "shell-restart",
                },
                "status": "active",
                "authority": {"changed_at": "2026-08-29"},
            }
        )
        code, _ = self.run_setup("--project-rule", project_rule, "--apply")
        self.assertEqual(code, 0)
        code, pack = self.run_context("--goal", "alpha", "--artifacts", "prd", "--stage", "requirements")
        self.assertEqual(code, 0)
        self.assertEqual(pack["effective_rules"]["project_rules"], [])
        self.assertEqual(pack["effective_rules"]["withheld_environment_rule_ids"], ["shell-restart"])

    def test_context_budget_uses_source_pointer_not_removed_body(self) -> None:
        self.write(
            "features/alpha/tasks.md",
            "---\nid: alpha\nproject_id: example-project\ncreated: 2026-08-24\n---\n# Tasks\n"
            + "\n".join(f"## T-{index:03d} Task\n" + ("detail " * 80) for index in range(20))
            + "\nReview verdict: READY\nImplementation gate: BLOCKED\n",
        )
        code, data = self.run_context(
            "--goal", "alpha", "--artifacts", "prd,tasks", "--stage", "implementation", "--max-chars", "4000"
        )
        self.assertEqual(code, 0)
        rendered = json.dumps(data, ensure_ascii=False, indent=2)
        self.assertLessEqual(len(rendered), 4000)
        self.assertTrue(data["required_expansions"])
        self.assertNotIn("item", data["required_expansions"][0])
        self.assertEqual(data["required_expansions"][0]["path"], "projects/example-project/features/alpha/tasks.md")

    def test_context_no_match_and_invalid_budget_fail_closed(self) -> None:
        code, data = self.run_context("--date", "2026-08-23", "--stage", "impact")
        self.assertEqual(code, 3)
        self.assertEqual(data["status"], "no_match")
        code, data = self.run_context("--goal", "alpha", "--stage", "impact", "--max-chars", "1999")
        self.assertEqual(code, 2)
        self.assertEqual(data["status"], "error")

    def test_resolve_returns_identity_without_selecting_documents(self) -> None:
        code, data = self.run_resolve()
        self.assertEqual(code, 0)
        self.assertEqual(data["status"], "resolved")
        self.assertEqual(data["mode"], "identity")
        self.assertEqual(data["project_id"], "example-project")
        self.assertEqual(data["documents"], [])
        self.assertEqual(data["source_verification"], "not-requested")

    def run_registry_select(
        self,
        registry_content: str,
        workspace: Path,
        *args: str,
        environment: dict[str, str] | None = None,
    ) -> tuple[int, dict]:
        registry = self.root / "workspaces.yaml"
        registry.write_text(registry_content, encoding="utf-8")
        clean_environment = os.environ.copy()
        for name in list(clean_environment):
            if name.startswith("PASEO_"):
                clean_environment.pop(name)
        if environment:
            clean_environment.update(environment)
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "select",
                "--record-root",
                str(self.root),
                "--registry",
                str(registry),
                "--workspace",
                str(workspace),
                *args,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            env=clean_environment,
        )
        return proc.returncode, json.loads(proc.stdout)

    def test_exact_created_date(self) -> None:
        code, data = self.run_select("--date", "260825")
        self.assertEqual(code, 0)
        self.assertEqual(data["documents"], ["projects/example-project/features/alpha/prd.md"])

    def test_now_goal_is_bounded(self) -> None:
        code, data = self.run_select("--now", "--goal", "alpha")
        self.assertEqual(code, 0)
        self.assertEqual(data["mode"], "now")
        self.assertEqual(data["documents"], [
            "projects/example-project/NOW/index.md",
            "projects/example-project/NOW/goals/alpha.md",
            "projects/example-project/NOW/system.md",
            "projects/example-project/NOW/validation.md",
        ])

    def test_now_without_goal_does_not_expand_all_goals(self) -> None:
        code, data = self.run_select("--now")
        self.assertEqual(code, 0)
        self.assertNotIn("projects/example-project/NOW/goals/alpha.md", data["documents"])

    def test_decision_filter(self) -> None:
        code, data = self.run_select("--date", "260825", "--decision", "D-003")
        self.assertEqual(code, 0)
        self.assertEqual(len(data["documents"]), 1)

    def test_no_match_fails_closed(self) -> None:
        code, data = self.run_select("--date", "260823")
        self.assertEqual(code, 3)
        self.assertEqual(data["status"], "no_match")
        self.assertEqual(data["documents"], [])

    def test_undated_requires_opt_in(self) -> None:
        code, data = self.run_select("--date", "260825", "--include-undated")
        self.assertEqual(code, 0)
        self.assertIn("projects/example-project/features/alpha/undated.md", data["documents"])

    def test_now_date_conflict(self) -> None:
        code, data = self.run_select("--now", "--date", "260825")
        self.assertEqual(code, 2)
        self.assertEqual(data["status"], "error")

    def test_invalid_date(self) -> None:
        code, data = self.run_select("--date", "260231")
        self.assertEqual(code, 2)
        self.assertIn("invalid calendar date", data["error"])

    def test_compare_requires_now_and_date(self) -> None:
        code, data = self.run_select("--compare")
        self.assertEqual(code, 2)
        self.assertEqual(data["status"], "error")

    def test_artifact_filter(self) -> None:
        code, data = self.run_select("--goal", "alpha", "--artifacts", "tasks")
        self.assertEqual(code, 0)
        self.assertEqual(data["documents"], ["projects/example-project/features/alpha/tasks.md"])

    def test_paseo_project_id_resolves_v2_registry_without_absolute_path(self) -> None:
        workspace = self.root / "paseo-workspace"
        workspace.mkdir()
        registry = """version: 2
bindings:
  paseo:
    prj_example: example-project
projects:
  example-project:
    sources:
      workspace:
        source_root: .
      primary:
        source_root: config
        repository_identity: github.com/example/project
"""
        code, data = self.run_registry_select(
            registry,
            workspace,
            "--paseo-project-id",
            "prj_example",
            "--now",
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["project_id"], "example-project")
        self.assertEqual(data["project_resolution"]["method"], "paseo-project-id")
        self.assertEqual(
            data["project_resolution"]["paseo_project_id"],
            "prj_example",
        )

    def test_launch_environment_can_supply_paseo_project_id(self) -> None:
        workspace = self.root / "paseo-workspace"
        workspace.mkdir()
        registry = """version: 2
bindings:
  paseo:
    prj_example: example-project
projects:
  example-project:
    sources:
      primary:
        source_root: .
"""
        code, data = self.run_registry_select(
            registry,
            workspace,
            "--now",
            environment={"PASEO_PROJECT_ID": "prj_example"},
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["project_resolution"]["method"], "paseo-project-id")
        self.assertIn("launch environment", " ".join(data["warnings"]))

    def test_paseo_cli_is_discovered_from_path_for_ambient_runtime(self) -> None:
        workspace = self.root / "paseo-workspace"
        workspace.mkdir()
        executable_dir = self.root / "bin"
        executable_dir.mkdir()
        paseo = executable_dir / "paseo"
        paseo.write_text(
            "#!/bin/sh\n"
            f"printf '%s\\n' '[{{\"projectId\":\"prj_example\",\"path\":\"{workspace}\"}}]'\n",
            encoding="utf-8",
        )
        paseo.chmod(0o755)
        registry = """version: 2
bindings:
  paseo:
    prj_example: example-project
projects:
  example-project:
    sources:
      primary:
        source_root: .
"""
        code, data = self.run_registry_select(
            registry,
            workspace,
            "--now",
            environment={
                "PASEO_AGENT_ID": "agent_example",
                "PATH": f"{executable_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            },
        )
        self.assertEqual(code, 0)
        self.assertEqual(data["project_id"], "example-project")
        self.assertEqual(data["project_resolution"]["method"], "paseo-project-id")
        self.assertIn("discovered from the daemon", " ".join(data["warnings"]))

    def test_unexpected_internal_failure_returns_structured_error(self) -> None:
        output = StringIO()
        with (
            patch.object(sys, "argv", [str(SCRIPT), "resolve", "--project", "example-project"]),
            patch.object(intent_context, "resolve", side_effect=NameError("sensitive detail")),
            redirect_stdout(output),
        ):
            code = intent_context.main()
        data = json.loads(output.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(data["status"], "error")
        self.assertEqual(data["error_code"], "internal_tool_error")
        self.assertEqual(data["operation"], "resolve")
        self.assertNotIn("sensitive detail", output.getvalue())

    def test_v2_source_repository_identity_resolves_nested_git_checkout(self) -> None:
        workspace = self.root / "workspace" / "config"
        workspace.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(workspace)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(workspace),
                "remote",
                "add",
                "origin",
                "https://github.com/example/project.git",
            ],
            check=True,
        )
        registry = """version: 2
projects:
  example-project:
    sources:
      primary:
        source_root: config
        repository_identity: github.com/example/project
"""
        code, data = self.run_registry_select(registry, workspace, "--now")
        self.assertEqual(code, 0)
        self.assertEqual(data["project_resolution"]["method"], "repository-identity")

    def test_declared_nested_source_resolves_from_logical_workspace(self) -> None:
        workspace = self.root / "workspace"
        source = workspace / "config"
        source.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(source)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(source),
                "remote",
                "add",
                "origin",
                "https://github.com/example/project.git",
            ],
            check=True,
        )
        registry = """version: 2
projects:
  example-project:
    sources:
      primary:
        source_root: config
        repository_identity: github.com/example/project
"""
        code, data = self.run_registry_select(registry, workspace, "--now")
        self.assertEqual(code, 0)
        self.assertEqual(data["project_resolution"]["method"], "repository-identity")

    def test_declared_source_symlink_cannot_escape_runtime_workspace(self) -> None:
        workspace = self.root / "workspace"
        workspace.mkdir()
        outside = self.root / "outside"
        outside.mkdir()
        subprocess.run(["git", "init", "-q", str(outside)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(outside),
                "remote",
                "add",
                "origin",
                "https://github.com/example/project.git",
            ],
            check=True,
        )
        (workspace / "config").symlink_to(outside, target_is_directory=True)
        registry = """version: 2
projects:
  example-project:
    sources:
      primary:
        source_root: config
        repository_identity: github.com/example/project
"""
        code, data = self.run_registry_select(registry, workspace, "--now")
        self.assertEqual(code, 2)
        self.assertIn("escapes runtime workspace", data["error"])

    def test_paseo_and_legacy_workspace_conflict_fails_closed(self) -> None:
        workspace = self.root / "paseo-workspace"
        workspace.mkdir()
        registry = f"""version: 2
bindings:
  paseo:
    prj_example: example-project
projects:
  example-project:
    sources:
      primary:
        source_root: .
  other-project:
    source_workspace: {workspace}
"""
        code, data = self.run_registry_select(
            registry,
            workspace,
            "--paseo-project-id",
            "prj_example",
            "--now",
        )
        self.assertEqual(code, 2)
        self.assertIn("identity conflict", data["error"])

    def test_v2_source_root_must_be_workspace_relative(self) -> None:
        workspace = self.root / "paseo-workspace"
        workspace.mkdir()
        registry = """version: 2
bindings:
  paseo:
    prj_example: example-project
projects:
  example-project:
    sources:
      primary:
        source_root: /absolute/path
"""
        code, data = self.run_registry_select(
            registry,
            workspace,
            "--paseo-project-id",
            "prj_example",
            "--now",
        )
        self.assertEqual(code, 2)
        self.assertIn("workspace-relative", data["error"])


if __name__ == "__main__":
    unittest.main()
