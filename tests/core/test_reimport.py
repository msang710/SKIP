import json
from pathlib import Path
import tempfile
import unittest
from tools.migrate_records import inventory,migrate
from tools.reimport_records import repair,terminal,parse_document,items
from skip_core.db import Database
from skip_core.service import Core
from skip_core.authority import Principal
from skip_core.errors import CoreError

class ReimportTests(unittest.TestCase):
    def test_semantic_records_exclusions_status_and_exact_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'projects/p/features/g';folder.mkdir(parents=True)
            (folder/'prd.md').write_text('---\ntitle: 재고 예약\nstatus: approved\n---\n# 재고 예약\n## Goal\n출고 중인 재고의 중복 배정을 방지한다.\n## Acceptance\n출고 중에는 예약이 유지된다.\n## Decisions\n| ID | Decision | Evidence and rationale | Status |\n|---|---|---|---|\n| D-001 | 출고 중 예약 유지 | 중복 배정 방지 | confirmed |\n## Requirements\n- R-001: 출고 중 예약 유지. D-001. Acceptance: 해제 요청을 거절한다.\n')
            (folder/'system_design.md').write_text('---\nstatus: approved\n---\n# 설계\n## 잠금\nR-001과 D-001을 만족하도록 잠금 안에서 재검사한다. T-001, T-002.\n')
            (folder/'tasks.md').write_text('---\nstatus: approved\n---\n# Tasks\n## T-001 잠금 구현\n- Connected requirements: R-001\n- Completion conditions: 중복 배정 없음\n- Verification: concurrency tests\n## T-002 회귀 검증\n- Dependencies: T-001\n- Verification: regression tests\n## T-003 재개 검증\n- Dependencies: T-002\n- Verification: resume tests\n')
            (folder/'old_tasks.md').write_bytes('\ufeff---\r\nstatus: superseded\r\n---\r\n# T-999 폐기 작업\r\n'.encode())
            (folder/'rejected_tasks.md').write_text('status: rejected\n# T-998 반려 작업\n')
            nowdir=root/'projects/p/NOW/goals';nowdir.mkdir(parents=True)
            (nowdir/'g.md').write_text('---\nstatus: partially-verified\nupdated: 2026-08-01\n---\n# 현재 기록\n## Verification\nPASS: concurrency tests\n## Limits\nNOT_RUN: physical printer\n')
            target=root/'test.db';migrate(root,target,inventory(root));report=repair(target)
            self.assertEqual(len(report['excluded']),2)
            with Database(target) as db:
                c=db.connection;core=Core(db);pr=Principal('p','test')
                goal=core.query('record',{'kind':'goal','id':'g'},pr)['data']
                self.assertIn('중복 배정을 방지',goal['fields']['intent'])
                self.assertNotIn('이관한 작업',goal['fields']['intent'])
                self.assertEqual(core.query('inbox',{'goal_id':'g'},pr)['data']['items'],[])
                work=core.query('record.list',{'goal_id':'g','kind':'work_item'},pr)['data']['items']
                self.assertEqual(len(work),3)
                self.assertEqual(c.execute('select count(*) from work_dependencies d join work_items h on h.project_id=d.project_id and h.id=d.depends_on_id join work_items own on own.project_id=d.project_id and own.id=d.work_item_id where own.current_revision=d.work_revision and d.depends_on_revision<>h.current_revision').fetchone()[0],0)
                self.assertEqual(c.execute('select count(*) from work_item_requirements').fetchone()[0],1)
                states={r['origin']['source_status'] for r in core.query('record.list',{'goal_id':'g','kind':'evidence'},pr)['data']['items']}
                self.assertIn('PASS',states);self.assertIn('NOT_RUN',states)
                self.assertFalse(any(r['freshness']=='current' for r in core.query('status',{'goal_id':'g'},pr)['data']['checks']))
                for table in ['authorizations','executions','selections']:
                    self.assertEqual(c.execute('select count(*) from '+table).fetchone()[0],0)
                visible=core.query('history',{'goal_id':'g'},pr)['data']['items']
                self.assertFalse(any('old_tasks' in r['source_path'] or 'rejected_tasks' in r['source_path'] for r in visible))
                self.assertEqual(c.execute('pragma integrity_check').fetchone()[0],'ok')
            with self.assertRaises(AssertionError):repair(target)
    def test_pending_verification_does_not_mean_completed(self):
        for state in ['implemented','partially-verified','구현 완료, CI 증거 대기','approved','draft']:
            self.assertFalse(terminal(state))
        for state in ['completed','superseded','rejected','완료','반려']:
            self.assertTrue(terminal(state))

    def test_reference_bullets_do_not_replace_task_definitions(self):
        text="- T-001의 결과를 확인한다.\n\n## T-001 원래 작업\n- Dependencies: none\n- Verification: tests\n\n## T-002 다음 작업\n- Dependencies: T-001\n"
        parsed=items(text,'T')
        self.assertEqual(len(parsed),2)
        self.assertEqual(parsed[0]['title'],'T-001 원래 작업')
        self.assertIn('Verification: tests',parsed[0]['body'])

    def test_letter_suffix_task_ids_are_preserved(self):
        parsed = items('## T-010A lease verification\n- Dependencies: T-010.\n## T-010 original task\n- Verification: tests\n', 'T')
        self.assertEqual([p['key'] for p in parsed], ['T-010A', 'T-010'])
        self.assertIn('Dependencies: T-010', parsed[0]['body'])
