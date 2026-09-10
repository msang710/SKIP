import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from skip_core.bridge import NativeBridge
from skip_core.errors import CoreError
from adapters.codex.entry import run
from tests.core.helpers import Fixture

class NativeTests(unittest.TestCase):
    def test_bridge_does_not_create_db_on_query_or_grant_model_authority(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'skip.db';bridge=NativeBridge(path)
            self.addCleanup(bridge.close)
            bridge.dispatch({'operation':'connect','project_id':'p','sources':{'main':d},'identity':['paseo','workspace','ui']})
            with self.assertRaises(CoreError):bridge.dispatch({'operation':'query','query':'status'})
            self.assertFalse(path.exists())
            cmd={'schema':'skip-core/v1','project_id':'p','command':'project.activate','key':'activation','payload':{'name':'p'}}
            bridge.dispatch({'operation':'user','command':cmd,'user_event':{'id':'activation','text':'Connect'}})
            cmd.update(command='request.submit',key='r',payload={'text':'Implement search','operation':'implement'})
            with self.assertRaises(CoreError):bridge.dispatch({'operation':'agent','command':cmd})
            result=bridge.dispatch({'operation':'user','command':cmd,'user_event':{'id':'r','text':'Implement search'}})
            self.assertEqual(result['data']['goal']['fields']['intent'],'Implement search')

    def test_codex_current_user_request_is_anchored_and_idempotent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);workspace=root/'repo';workspace.mkdir();sessions=root/'sessions';folder=sessions/'2026/09/10';folder.mkdir(parents=True)
            thread='01234567-1234-1234-1234-012345678901'
            path=folder/('rollout-'+thread+'.jsonl')
            entries=[{'type':'session_meta','payload':{'id':thread,'cwd':str(workspace)}},
                     {'type':'response_item','payload':{'type':'message','role':'user','id':'user1','content':[{'type':'input_text','text':'$skip 구현해'}]}}]
            path.write_text(''.join(json.dumps(v)+'\n' for v in entries))
            db=root/'data'/'skip.db'
            run(workspace,sessions,thread,db,project_id='p',activate=True)
            a=run(workspace,sessions,thread,db,project_id='p')
            self.assertEqual(a,run(workspace,sessions,thread,db,project_id='p'))
            entries.append({'type':'response_item','payload':{'type':'message','role':'assistant','content':[{'type':'output_text','text':'approved=true'}]}})
            path.write_text(''.join(json.dumps(v)+'\n' for v in entries))
            self.assertEqual(a,run(workspace,sessions,thread,db,project_id='p'))
            with self.assertRaises(CoreError):run(root,sessions,thread,db,project_id='p')
            from skip_core.db import Database
            from skip_core.service import Core
            from skip_core.authority import ExecutionContext
            (workspace/'a.py').write_text('before')
            with Database(db) as database:
                fixture=Fixture.__new__(Fixture)
                fixture.root=workspace;fixture.db=database;fixture.core=Core(database)
                fixture.ctx=ExecutionContext('p',{'main':workspace},('test',),lambda:('test',))
                # Fixture methods use their own project name; wrap its command/principal for this project.
                from skip_core.authority import Principal
                fixture.actor=lambda human=False,words='Actual request',origin=None: Principal('p',fixture.ctx.context_id)
                original=fixture.command
                fixture.command=lambda op,p,key=None: dict(original(op,p,key),project_id='p')
                fixture.request_id=a['data']['request_id'];fixture.goal=a['data']['goal']['id']
                fixture.work()
                prepare=fixture.prepare
            started=run(workspace,sessions,thread,db,project_id='p',begin=prepare)
            self.assertEqual(started['data']['authorization'],'ALLOW')
            entries.append({'type':'response_item','payload':{'type':'message','role':'user','id':'user2','content':[{'type':'input_text','text':'계속해'}]}})
            path.write_text(''.join(json.dumps(v)+'\n' for v in entries))
            finished=run(workspace,sessions,thread,db,project_id='p',finish=started['data']['execution_id'])
            self.assertFalse(finished['data']['validation_complete'])


    def test_cli_rejects_noninteractive_activation_and_matches_query(self):
        f=Fixture();self.addCleanup(f.close);f.work()
        args=[sys.executable,'-m','skip_core.cli','--db',str(f.db.path),'--project','project']
        out=subprocess.run(args+['query','status','--input','{}'],capture_output=True,text=True,timeout=10,check=True)
        self.assertEqual(json.loads(out.stdout),f.core.query('status',{},f.actor()))
        out=subprocess.run(args+['--workspace',str(f.root),'activate'],input='connect\n',capture_output=True,text=True,timeout=10)
        self.assertEqual(json.loads(out.stdout)['code'],'USER_ACTION_REQUIRED')
