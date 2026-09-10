import contextlib
import io
from pathlib import Path
import runpy
import unittest
from skip_core.db import restore,Database
from tests.core.helpers import Fixture

class SchemaTests(unittest.TestCase):
    def test_all_approved_sql_contract_cases(self):
        with contextlib.redirect_stdout(io.StringIO()):
            result=runpy.run_path(str(Path(__file__).with_name('schema_cases.py')))
        self.assertEqual(len(result['checks']),24)

    def test_restore_does_not_activate_or_overwrite_database(self):
        f=Fixture();self.addCleanup(f.close);f.work()
        backup=f.root/'backup.db';f.db.backup(backup)
        target=f.root/'restored.db';result=restore(backup,target)
        self.assertFalse(result['activated'])
        with Database(target) as db:self.assertEqual(db.connection.execute('SELECT count(*) FROM work_items').fetchone()[0],1)
        with self.assertRaises(Exception):restore(backup,target)
