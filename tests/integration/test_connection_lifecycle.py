import asyncio
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from skip_core.authority import ExecutionContext
from skip_core.db import Database
from skip_core.errors import CoreError
from tests.core.helpers import Fixture


class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.f = Fixture()
        self.addCleanup(self.f.close)
        self.f.work()

    def test_cli_retries_across_processes_and_conflicting_payload(self):
        f = self.f
        command = f.command('observation.record', {'paths':[dict(p,access='read') for p in f.scope], 'summary':'original'}, key='replay')
        args = [sys.executable, '-m', 'skip_core.cli', '--db', str(f.db.path), '--project','project',
                '--workspace',str(f.root),'--receipt-scope','client-one','command']
        env = {k:v for k,v in os.environ.items() if k != 'CODEX_THREAD_ID'}
        def call(value):
            return json.loads(subprocess.run(args, input=json.dumps(value),capture_output=True,text=True,env=env,timeout=10).stdout)
        a = call(command)
        self.assertEqual(a['status'],'ok')
        self.assertEqual(a, call(command))
        self.assertEqual(f.db.connection.execute("SELECT count(*) FROM command_receipts WHERE command_key='replay'").fetchone()[0],1)
        command['payload']['summary']='different'
        self.assertEqual(call(command)['code'],'CONFLICT')
        command['command']='execution.prepare';command['payload']=f.prepare
        self.assertEqual(call(command)['code'],'USER_ACTION_REQUIRED')
        args.remove('--receipt-scope');args.remove('client-one')
        self.assertEqual(call(command)['code'],'CALLER_UNVERIFIED')

    def test_active_runtime_diagnostics_ignores_cwd_module_shadow(self):
        f=self.f
        shadow=f.root/'skip_core';shadow.mkdir()
        (shadow/'__init__.py').write_text('raise RuntimeError("old checkout imported")')
        env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[2])}
        args=[sys.executable,'-P','-B','-m','skip_core.cli','--db',str(f.db.path),'diagnose']
        result=subprocess.run(args,cwd=f.root,env=env,capture_output=True,text=True,timeout=10,check=True)
        value=json.loads(result.stdout)
        self.assertEqual(value['status'],'ok')
        self.assertEqual(value['actual_schema_versions'],[1,2,3,4,5,6])
        self.assertEqual(value['core_root'],str(Path(__file__).resolve().parents[2]))

    def test_simultaneous_cli_retries_write_once(self):
        f=self.f
        command=f.command('observation.record', {'paths':[dict(p,access='read') for p in f.scope], 'summary':'parallel'},key='parallel-key')
        args=[sys.executable,'-m','skip_core.cli','--db',str(f.db.path),'--project','project',
              '--workspace',str(f.root),'--receipt-scope','parallel-client','command']
        env={k:v for k,v in os.environ.items() if k!='CODEX_THREAD_ID'}
        from concurrent.futures import ThreadPoolExecutor
        def call(_):
            r=subprocess.run(args,input=json.dumps(command),capture_output=True,text=True,env=env,timeout=10,check=True)
            return json.loads(r.stdout)
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(call,range(2)))
        self.assertEqual(results[0],results[1])
        self.assertEqual(f.db.connection.execute("SELECT count(*) FROM command_receipts WHERE command_key='parallel-key'").fetchone()[0],1)

    def test_verified_codex_scope_is_stable_but_not_shared_with_other_threads(self):
        from adapters.common.caller import caller_scope
        f=self.f
        sessions=f.root/'codex/sessions/2026/09/10';sessions.mkdir(parents=True)
        def host(thread):
            rows=[{'type':'session_meta','payload':{'id':thread,'cwd':str(f.root)}},
                  {'type':'response_item','payload':{'type':'message','role':'user','id':'u1','content':[{'type':'input_text','text':'구현해'}]}}]
            (sessions/('rollout-'+thread+'.jsonl')).write_text(''.join(json.dumps(r)+'\n' for r in rows))
        one='01234567-1234-1234-1234-012345678901';two='01234567-1234-1234-1234-012345678902'
        host(one);host(two)
        with patch.dict(os.environ,{'CODEX_HOME':str(f.root/'codex'),'CODEX_THREAD_ID':one}):
            a=caller_scope(f.root,'cli');self.assertTrue(a[1])
            self.assertEqual(a,caller_scope(f.root,'cli'))
            self.assertNotEqual(a,caller_scope(f.root,'mcp'))
            with patch.dict(os.environ,{'CODEX_THREAD_ID':two}):self.assertNotEqual(a,caller_scope(f.root,'cli'))
            self.assertFalse(caller_scope(f.root.parent,'cli')[1])

    def test_execution_connection_does_not_claim_another_caller_or_restore_rights(self):
        f=self.f;x=f.start();payload={'execution_id':x['execution_id']}
        def status(ctx):return f.core.query('execution.status',payload,f.actor(),ctx)['data']
        self.assertEqual(status(f.ctx)['connection']['state'],'current')
        other=ExecutionContext('project',{'main':f.root},f.target,lambda:f.target,caller_verified=True)
        self.assertEqual(status(other)['connection']['state'],'revalidation_required')
        self.assertFalse(status(other)['connection_current'])
        other.verify=lambda:('other-thread',)
        self.assertEqual(status(other)['connection']['state'],'target_changed')
        self.assertEqual(status(None)['connection']['state'],'unverified')
        from skip_core.delivery import Delivery
        other.verify=lambda:f.target
        with self.assertRaises(CoreError):Delivery(f.core,other).claim(x['execution_id'])

    def test_source_renewal_does_not_extend_native_context(self):
        f=self.f
        c=ExecutionContext('project',{'main':f.root},('source',),lambda:('source',),renewable_source=True)
        old=c.fingerprint;c.expires_at=0;c.refresh_source();c.check()
        self.assertNotEqual(old,c.fingerprint)
        c.close()
        with self.assertRaises(CoreError):c.refresh_source()
        f.ctx.renewable_source=True;f.ctx.expires_at=0
        with self.assertRaises(CoreError):f.ctx.refresh_source()

    def test_mcp_queries_after_expiry_and_reconnect_replay(self):
        from skip_mcp.server import create_server
        async def scenario():
            f=self.f
            with patch.dict(os.environ,{'CODEX_THREAD_ID':''}):
                server=create_server(f.db.path,'project',f.root,receipt_scope='mcp-client')
                payload={'paths':[dict(p,access='read') for p in f.scope],'summary':'observation','key':'retry'}
                def value(result):
                    if isinstance(result, tuple):
                        if isinstance(result[1], dict): return result[1]
                        result=result[0]
                    return json.loads(result[0].text)
                first=value(await server.call_tool('skip_observe',payload))
                with patch('skip_core.authority.time.monotonic',return_value=10**12):
                    result=value(await server.call_tool('skip_status',{}))
                    self.assertEqual(result['status'],'ok')
                reconnect=create_server(f.db.path,'project',f.root,receipt_scope='mcp-client')
                self.assertEqual(first,value(await reconnect.call_tool('skip_observe',payload)))
                renamed=f.root/'renamed';renamed.mkdir()
                # Changed source inode is detected, rather than silently renewed.
                with patch('pathlib.Path.stat',side_effect=FileNotFoundError):
                    result=value(await server.call_tool('skip_status',{}))
                    self.assertEqual(result['code'],'SOURCE_UNAVAILABLE')
        asyncio.run(scenario())


class DatabaseErrors(unittest.TestCase):
    def test_access_error_is_not_schema_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db'
            with Database(path,create=True):pass
            exc=sqlite3.OperationalError('unable to open database file')
            exc.sqlite_errorcode=sqlite3.SQLITE_CANTOPEN;exc.sqlite_errorname='SQLITE_CANTOPEN'
            with patch('sqlite3.connect',side_effect=exc):
                with self.assertRaises(CoreError) as result:Database(path)
            self.assertEqual(result.exception.code,'DB_ACCESS_DENIED')
            self.assertEqual(result.exception.details['sqlite_errorname'],'SQLITE_CANTOPEN')
            self.assertEqual(result.exception.details['database_path'],str(path))

    def test_corruption_and_actual_schema_mismatch_are_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db';path.write_bytes(b'not a database'*100)
            with self.assertRaises(CoreError) as result:Database(path)
            self.assertEqual(result.exception.code,'DB_CORRUPT')
            path.unlink()
            with Database(path,create=True):pass
            original=Database.migrations
            def mismatched():return [(v,sql,'wrong' if v==1 else sha) for v,sql,sha in original()]
            with patch.object(Database,'migrations',side_effect=mismatched):
                with self.assertRaises(CoreError) as result:Database(path)
            self.assertEqual(result.exception.code,'UNSUPPORTED_SCHEMA')
            self.assertEqual(result.exception.details['actual_schema_versions'],[1,2,3,4,5,6])
            path.unlink();path.touch()
            with self.assertRaises(CoreError) as result:Database(path)
            self.assertEqual(result.exception.code,'UNSUPPORTED_SCHEMA')
            self.assertEqual(result.exception.details['actual_schema_versions'],[])

    def test_real_readonly_and_lock_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'db'
            with Database(path,create=True) as db:
                db.connection.execute('PRAGMA query_only=ON')
                with self.assertRaises(CoreError) as result:
                    with db.transaction():db.connection.execute('CREATE TABLE forbidden (id int)')
                self.assertEqual(result.exception.code,'DB_READ_ONLY')
                db.connection.execute('PRAGMA query_only=OFF')
                second=sqlite3.connect(path)
                try:
                    second.execute('BEGIN IMMEDIATE');db.connection.execute('PRAGMA busy_timeout=1')
                    with self.assertRaises(CoreError) as result:
                        with db.transaction():pass
                    self.assertEqual(result.exception.code,'DB_BUSY')
                finally:second.close()
