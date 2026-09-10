import json
import subprocess
import sys
import unittest
from tests.core.helpers import Fixture
from skip_core.errors import CoreError

class RelationTests(unittest.TestCase):
    def setUp(self):self.f=Fixture();self.addCleanup(self.f.close);self.f.request()
    def decision(self):
        return self.f.publish('decision',{'question':'Release stock?','rationale':'Prevent duplicate allocation','risk_summary':'Inventory risk'},
          {'options':[{'option_id':o,'label':o,'description':o,'consequences':o,'recommended':int(i==0),'position':i} for i,o in enumerate(('keep','release'))]})
    def test_full_plan_exact_selected_option_and_changed_basis(self):
        d=self.decision();selection=self.f.call('decision.select',{'decision_id':d['id'],'revision':1,'option_id':'keep'},True)
        r=self.f.publish('requirement',{'title':'Keep stock','statement':'Keep reserved stock','rationale':'Selected business rule'},
          {'criteria':[{'criterion_id':'c','description':'no double allocation','given_text':'shipping','when_text':'release','then_text':'keep','required':1}],
           'decisions':[{'decision_id':d['id'],'decision_revision':1,'rationale':'shipping rule'}],
           'selections':[{'selection_id':selection['selection_id'],'rationale':'keep'}]})
        plan=self.f.publish('plan',{'title':'Lock','design_body':'locked revalidation','scope_description':'allocation','alternatives_body':'race before lock','rollback_body':'restore'},
          {'items':[{'item_id':'item','title':'lock','design_body':'inside lease','verification_body':'concurrency','position':0}],
           'requirements':[{'requirement_id':r['id'],'requirement_revision':1,'rationale':'keep'}]})
        self.f.work(True,[{'requirement_id':r['id'],'requirement_revision':1,'rationale':'keep'}],
                        [{'plan_id':plan['id'],'plan_revision':1,'plan_item_id':'item','rationale':'lock'}])
        self.f.start()
        self.f.call('decision.select',{'decision_id':d['id'],'revision':1,'option_id':'release'},True)
        from skip_core.execution import basis
        with self.assertRaises(CoreError) as error:basis(self.f.core,self.f.w['id'],1)
        self.assertEqual(error.exception.code,'STALE')
        # Original immutable requirement continues to identify the old exact selection.
        value=self.f.core.query('record',{'kind':'requirement','id':r['id']},self.f.actor())['data']
        self.assertEqual(value['children']['selections'][0]['selection_id'],selection['selection_id'])

    def test_select_and_execute_roll_back_together_on_stale_source(self):
        d=self.decision();self.f.work();(self.f.root/'a.py').write_text('changed')
        p={**self.f.prepare,'selection':{'decision_id':d['id'],'revision':1,'option_id':'keep'}}
        with self.assertRaises(CoreError):self.f.call('execution.prepare',p,True)
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM selections').fetchone()[0],0)

    def test_reselecting_same_option_preserves_existing_basis(self):
        d=self.decision();p={'decision_id':d['id'],'revision':1,'option_id':'keep'}
        a=self.f.call('decision.select',p,True);b=self.f.call('decision.select',p,True)
        self.assertEqual(a['selection_id'],b['selection_id'])

    def test_two_processes_cannot_publish_the_same_revision(self):
        self.f.work();w=self.f.w
        command=self.f.command('record.propose_revision',{'kind':'work_item','id':w['id'],'expected_revision':1,'request_id':self.f.request_id,
            'goal_id':self.f.goal,'fields':w['fields'],'children':w['children']})
        code='''import sys,json
from skip_core.db import Database
from skip_core.service import Core
from skip_core.authority import Principal
from skip_core.errors import CoreError
p=json.loads(sys.stdin.readline())
with Database(sys.argv[1]) as db:
 try: print(Core(db).execute(p,Principal('project',sys.argv[2]))['status'])
 except CoreError as e: print(e.code)
'''
        children=[subprocess.Popen([sys.executable,'-c',code,str(self.f.db.path),f'worker-{i}'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for i in range(2)]
        for child in children:child.stdin.write(json.dumps(command)+'\n');child.stdin.flush()
        outputs=[]
        for child in children:
            out,err=child.communicate(timeout=10);self.assertEqual(child.returncode,0,err);outputs.append(out.strip())
        self.assertCountEqual(outputs,['ok','STALE'])

    def test_process_death_rolls_back_uncommitted_business_rows(self):
        before=self.f.db.connection.execute('SELECT count(*) FROM projects').fetchone()[0]
        code="import sqlite3,os,sys;c=sqlite3.connect(sys.argv[1]);c.execute('BEGIN IMMEDIATE');c.execute(\"INSERT INTO projects VALUES('uncommitted','test','active','now')\");os._exit(9)"
        result=subprocess.run([sys.executable,'-c',code,str(self.f.db.path)],timeout=10)
        self.assertEqual(result.returncode,9)
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM projects').fetchone()[0],before)

if __name__=='__main__':unittest.main()
