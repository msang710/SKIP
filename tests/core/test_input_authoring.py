import copy
import json
import unittest
from unittest.mock import patch
from tests.core.helpers import Fixture
from skip_core.common import digest
from skip_core.errors import CoreError
from skip_core.input_contract import classify, normalize
from adapters.codex.entry import run


class InputAuthoringTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture(); self.addCleanup(self.f.close)

    def capture(self, words):
        actor=self.f.actor(True,words)
        return self.f.core.execute(self.f.command('input.ingest',{}),actor,self.f.ctx)['data']

    def payload(self, words='새 목표에 기록해', acts=None):
        i=self.capture(words)
        body={k:v for k,v in classify(normalize(words,'project')).items() if k in ('acts','constraints','targets','evidence_spans','unresolved')}
        body.update(acts=acts or ['create_goal'],unresolved=[])
        return {'input_id':i['input_id'],'input_digest':i['digest'],'expected_revision':0,'body':body,'target':{'mode':'create','fields':{'title':'빛과 인과관계로 이어지는 공간 UX','intent':'채택한 여섯 기능 기록','success_definition':'확정된 원칙과 추가 설계 경계를 구분'}},'records':[]}

    def count(self,table):return self.f.db.connection.execute('SELECT count(*) FROM '+table).fetchone()[0]

    def test_unknown_is_recoverable_and_record_only_does_not_create_plan(self):
        for words in ['새 목표에 기록해','이 내용으로 새 목표 생성해','앞의 여섯 기능을 새 목표로 묶어서 기록해']:
            with self.subTest(words=words):
                p=self.payload(words)
                entry=self.f.core.query('entry.inspect',{'input_id':p['input_id']},self.f.actor())['data']
                self.assertEqual(entry['suggestion']['acts'],['unresolved'])
                self.assertEqual(entry['next_tool'],'skip_enter')
                r=self.f.call('entry.submit',p)
                self.assertTrue(r['goal_created']); self.assertEqual(r['authority'],'records_only')
                request=self.f.db.connection.execute('SELECT * FROM requests WHERE id=?',(r['authoring_base']['request_id'],)).fetchone()
                self.assertEqual(request['operation'],'record'); self.assertEqual(request['intent'],words)
                self.assertEqual(self.f.call('entry.submit',p),r) # new transport key, same input
        self.assertEqual(self.count('goals'),3)
        self.assertEqual(self.count('plans'),0); self.assertEqual(self.count('authorizations'),0)

    def test_atomic_bundle_and_input_dedup(self):
        from tests.core.test_authoring import AuthoringTests
        p=self.payload(acts=['create_goal','design']); p['records']=[AuthoringTests.plan(self)]
        bad=copy.deepcopy(p); bad['records'].append({'bad':True})
        with self.assertRaises(CoreError): self.f.call('entry.submit',bad)
        for table in ['requests','goals','plans','input_intent_versions','input_materializations']:self.assertEqual(self.count(table),0)
        r=self.f.call('entry.submit',p); self.assertEqual(len(r['records']),1)
        changed=copy.deepcopy(p); changed['target']['fields']['title']='different'
        with self.assertRaises(CoreError): self.f.call('entry.submit',changed)
        self.assertEqual(self.count('goals'),1)
        stage=self.f.core.query('stage.assess',r['authoring_base'],self.f.actor())['data']
        self.assertEqual(len(stage['output_records']['plan']),1)

    def test_quote_constraint_digest_and_unresolved(self):
        p=self.payload('> 구현해\n새 목표에 기록해. 배포하지 마', ['create_goal'])
        bad=copy.deepcopy(p); bad['body']['evidence_spans']=[{'part_id':'0','start':0,'end':4}]
        with self.assertRaises(CoreError):self.f.call('entry.submit',bad)
        bad=copy.deepcopy(p); bad['body']['constraints']=[]
        with self.assertRaises(CoreError):self.f.call('entry.submit',bad)
        bad=copy.deepcopy(p); bad['input_digest']='0'*64
        with self.assertRaises(CoreError):self.f.call('entry.submit',bad)
        bad=copy.deepcopy(p); bad['body']['unresolved']=['which goal?']
        with self.assertRaises(CoreError):self.f.call('entry.submit',bad)
        bad['target']={'mode':'none'}
        r=self.f.call('entry.submit',bad);self.assertEqual(r['next_action'],'resolve_meaning')
        self.assertEqual(self.count('goals'),0)
        p['expected_revision']=1
        self.f.call('entry.submit',p)
        self.assertEqual(self.count('authorizations'),0)

    def test_existing_goal_and_stale_version(self):
        r=self.f.request(); p=self.payload('이 목표에 계획 작성해',['design'])
        from tests.core.test_authoring import AuthoringTests
        p['records']=[AuthoringTests.plan(self)]
        p['target']={'mode':'existing','goal_id':r['goal']['id'],'revision':1}
        saved=self.f.call('entry.submit',p)
        self.assertEqual(saved['goal']['id'],r['goal']['id']);self.assertEqual(self.count('goals'),1)
        other=self.payload('다음 설계',['design']);other['target']=dict(p['target'],revision=5)
        with self.assertRaises(CoreError):self.f.call('entry.submit',other)

    def test_native_adapter_to_agent_core_submission(self):
        words='앞의 여섯 기능을 새 목표에 기록해'
        with patch('adapters.codex.entry.current_user',return_value={'id':'u-actual','text':words}):
            entry=run(self.f.root,self.f.root,'test-thread',self.f.db.path,project_id='project')['data']['entry_basis']
        self.assertEqual(self.count('goals'),0)
        self.assertEqual(entry['input']['digest'],digest(words))
        body={k:entry['suggestion'][k] for k in ('acts','constraints','targets','evidence_spans','unresolved')}
        body.update(acts=['create_goal'],unresolved=[])
        p={'input_id':entry['input_id'],'input_digest':entry['input']['digest'],'expected_revision':0,'body':body,'target':{'mode':'create','fields':{'title':'여섯 기능','intent':words,'success_definition':'기록'}},'records':[]}
        self.f.call('entry.submit',p);self.assertEqual(self.count('goals'),1)

    def test_bare_implementation_and_no_deploy(self):
        p=classify(normalize('구현\n배포는 아직','project'))
        self.assertEqual(p['acts'],['implement']); self.assertIn('deploy',p['constraints'])

    def test_goal_only_cannot_smuggle_plan(self):
        from tests.core.test_authoring import AuthoringTests
        p=self.payload();p['records']=[AuthoringTests.plan(self)]
        with self.assertRaises(CoreError):self.f.call('entry.submit',p)
        self.assertEqual(self.count('goals'),0)

    def test_cli_and_native_bridge_share_captured_input_contract(self):
        import subprocess,sys
        from skip_core.bridge import NativeBridge
        bridge=NativeBridge(self.f.db.path);self.addCleanup(bridge.close)
        bridge.dispatch({'operation':'connect','project_id':'project','sources':{'main':str(self.f.root)},'identity':['paseo','workspace','ui']})
        words='이 항목들을 목표로 기록해'
        command=self.f.command('input.ingest',{})
        ticket=bridge.dispatch({'operation':'card','command':command})['ticket']
        value=bridge.dispatch({'operation':'user','command':command,'ticket':ticket,'user_event':{'id':'native-entry','text':words}})['data']
        body={k:v for k,v in classify(normalize(words,'project')).items() if k in ('acts','constraints','targets','evidence_spans','unresolved')}
        body.update(acts=['create_goal'],unresolved=[])
        payload={'input_id':value['input_id'],'input_digest':value['digest'],'expected_revision':0,'body':body,'target':{'mode':'create','fields':{'title':'Native input','intent':words,'success_definition':'Recorded'}},'records':[]}
        out=subprocess.run([sys.executable,'-m','skip_core.cli','--db',str(self.f.db.path),'--project','project','--workspace',str(self.f.root),'--receipt-scope','test','enter','--submission-id','cli-enter'],input=json.dumps(payload),text=True,capture_output=True,timeout=10)
        self.assertEqual(out.returncode,0,out.stdout+out.stderr)
        self.assertTrue(json.loads(out.stdout)['data']['goal_created'])
        self.assertEqual(self.count('authorizations'),0)

    def test_v7_candidate_preserves_rows_and_old_writer_rejects_it(self):
        from skip_core.db import Database
        from skip_core.upgrade import candidate
        migrations=Database.migrations()
        with patch.object(Database,'migrations',return_value=migrations[:7]), patch('skip_core.record_state.metadata',return_value=None):
            old=Fixture();self.addCleanup(old.close);old.work()
        tables=[r[0] for r in old.db.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'schema_migrations'")]
        before={t:[tuple(r) for r in old.db.connection.execute('SELECT * FROM '+t)] for t in tables}
        path=old.root/'candidate.db';candidate(old.db.path,path)
        with Database(path) as db:
            for t,rows in before.items():self.assertEqual(rows,[tuple(r) for r in db.connection.execute('SELECT * FROM '+t)],t)
            self.assertFalse(db.connection.execute('pragma foreign_key_check').fetchall())
            self.assertEqual(db.connection.execute('pragma foreign_keys').fetchone()[0],1)
        with patch.object(Database,'migrations',return_value=migrations[:7]), patch('skip_core.record_state.metadata',return_value=None):
            with self.assertRaises(CoreError):Database(path)

    def test_invalid_migration_rolls_back_rebuild(self):
        import sqlite3
        from skip_core.db import Database
        migrations=Database.migrations()
        with patch.object(Database,'migrations',return_value=migrations[:7]), patch('skip_core.record_state.metadata',return_value=None):
            old=Fixture();self.addCleanup(old.close);old.work()
        invalid=list(migrations)
        v,sql,checksum=invalid[-1]; invalid[-1]=(v,sql+'\nINSERT INTO input_intent_versions VALUES (\'project\',\'missing\',1,\'{}\',\'digest\',\'missing\');\n',checksum)
        with patch.object(Database,'migrations',return_value=invalid):
            with self.assertRaises(CoreError):Database(old.db.path,create=True)
        self.assertEqual(old.db.connection.execute('SELECT max(version) FROM schema_migrations').fetchone()[0],7)
        self.assertEqual(old.db.connection.execute('SELECT count(*) FROM requests').fetchone()[0],1)
        self.assertFalse(old.db.connection.execute('pragma foreign_key_check').fetchall())
