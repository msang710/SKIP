import hashlib
from pathlib import Path
import tempfile
import unittest
from tools.migrate_records import inventory,migrate
from skip_core.db import Database
from skip_core.service import Core
from skip_core.authority import Principal
from skip_core.errors import CoreError

class MigrationTests(unittest.TestCase):
    def test_exact_bytes_relationships_and_no_imported_authority(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'old';feature=root/'projects/p/features/real-goal';feature.mkdir(parents=True)
            prd='---\ntitle: 제품 요구\nstatus: approved\n---\n# 결정\nD-003: 기존 재고 유지\n# 검증\nPASS (과거)\n'
            (feature/'prd.md').write_text(prd)
            (feature/'system_design.md').write_text('# 설계\n[요구](prd.md)\n본문\n')
            (feature/'tasks.md').write_text('# 작업\n승인 없이 자동 실행하지 않음\n')
            (feature/'image.png').write_bytes(b'\x89PNG\x00\xff')
            git=feature/'.git';git.mkdir();(git/'config').write_text('not business data')
            inv=inventory(root);target=Path(directory)/'candidate.db'
            result=migrate(root,target,inv)
            self.assertEqual(result['files'],4);self.assertEqual(result['excluded_git_files'],1)
            with Database(target) as db:
                core=Core(db);principal=Principal('p','read-only')
                status=core.query('status',{},principal)['data']
                self.assertEqual(len(status['goals']),1)
                self.assertEqual(status['facts'],[]);self.assertEqual(status['checks'],[])
                for table in ('authorizations','selections','executions','evidence'):
                    self.assertEqual(db.connection.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
                doc=db.connection.execute("SELECT * FROM imported_documents WHERE source_path LIKE '%prd.md'").fetchone()
                self.assertEqual(bytes(doc['content']),prd.encode())
                read=core.query('history.record',{'id':doc['id']},principal)['data']
                self.assertIn('D-003',read['body']);self.assertEqual(read['historical_status'],'approved');self.assertFalse(read['authority'])
                self.assertEqual(db.connection.execute("SELECT count(*) FROM imported_links WHERE resolution='resolved'").fetchone()[0],1)
                self.assertFalse(core.query('context',{'goal_id':'real-goal','stage':'implementation','budget':1024},principal)['data']['complete'])
                self.assertEqual(db.connection.execute("SELECT lifecycle FROM requirements").fetchone()[0],'held')
                with self.assertRaises(CoreError):core.query('history.record',{'id':doc['id']},Principal('other','read-only'))
            self.assertEqual((feature/'prd.md').read_text(),prd)
            with self.assertRaises(CoreError):migrate(root,target,inv)

    def test_changed_input_and_symlinks_fail_before_import(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);p=root/'projects/p/NOW';p.mkdir(parents=True)
            file=p/'system.md';file.write_text('old');manifest=inventory(root);file.write_text('changed')
            with self.assertRaises(CoreError):migrate(root,root/'candidate.db',manifest)
            link=p/'escape.md';link.symlink_to(root/'outside')
            with self.assertRaises(CoreError):inventory(root)
