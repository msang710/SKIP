from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from skip_core.db import Database,restore
from skip_core.upgrade import candidate
from skip_core.service import Core
from tests.core.helpers import Fixture

class UpgradeTests(unittest.TestCase):
    def test_v4_copy_upgrade_preserves_original_and_records(self):
        original=Database.migrations
        with patch.object(Database,'migrations',side_effect=lambda:original()[:4]):
            f=Fixture();self.addCleanup(f.close);f.request()
            path=f.root/'candidate.db'
            before=list(f.db.connection.execute('SELECT id,intent FROM requests'))
        result=candidate(f.db.path,path)
        self.assertFalse(result['activated'])
        self.assertEqual(f.db.connection.execute('SELECT max(version) FROM schema_migrations').fetchone()[0],4)
        with Database(path) as db:
            self.assertEqual([tuple(r) for r in db.connection.execute('SELECT id,intent FROM requests')],[tuple(r) for r in before])
            self.assertEqual(db.connection.execute('SELECT count(*) FROM failure_occurrences').fetchone()[0],0)
            backup=f.root/'backup.db';db.backup(backup)
        restore(backup,f.root/'restored.db')
        with self.assertRaises(FileExistsError):candidate(f.db.path,path)
    def test_selector_is_context_not_action(self):
        from adapters.codex.provenance import infer_operation
        selector='$skip --project p query record --input \'{"kind":"plan","id":"x","revision":3}\''
        self.assertEqual(infer_operation(selector+'\n구현해'),'implement')
        self.assertEqual(infer_operation(selector),'answer')
        self.assertEqual(infer_operation(selector+'\n구현하지 말고 검토해'),'plan')
    def test_current_turn_keeps_misclassified_request_without_changing_intent(self):
        f=Fixture();self.addCleanup(f.close)
        human=f.actor(True,words='구현해');f.ctx.can_continue=True
        req=f.core.execute(f.command('request.submit',{'text':'구현해','operation':'plan'}),human,f.ctx)['data']
        f.request_id=req['request_id'];f.goal=req['goal']['id'];f.work()
        result=f.core.execute(f.command('execution.begin_current',f.prepare),human,f.ctx)['data']
        self.assertEqual(result['state'],'running')
        self.assertEqual(f.db.connection.execute('SELECT count(*) FROM requests').fetchone()[0],1)
