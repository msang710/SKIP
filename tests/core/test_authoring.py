import unittest
from tests.core.helpers import Fixture
from skip_core.errors import CoreError

class AuthoringTests(unittest.TestCase):
 def setUp(self):
  self.f=Fixture();self.addCleanup(self.f.close);self.f.request();self.base={'goal_id':self.f.goal,'request_id':self.f.request_id}
 def plan(self):return {'client_ref':'p','kind':'plan','fields':{'title':'Plan','design_body':'Body','scope_description':'Local','alternatives_body':'None','rollback_body':'Revert'},'children':{'items':[{'item_id':'step','title':'Step','design_body':'Implement','verification_body':'Test'}]}}
 def call(self,op,**p):return self.f.call('authoring.'+op,{'base':self.base,**p})
 def test_plan_and_fourteen_tasks_one_submission(self):
  rows=[self.plan()]
  for i in range(14):rows.append({'client_ref':f'w{i}','kind':'work_item','fields':{'title':f'Work {i}','operation':'implement','instruction_body':'Change','completion_definition':'Test','workflow_depth':'compact'},'children':{'plan_items':[{'plan_id':'$p','plan_item_id':'step','rationale':'plan'}],'checks':[{'description':'test','surface':'unit','required':1}],**({'dependencies':[{'depends_on_id':f'$w{i-1}','reason':'previous'}]} if i else {})}})
  r=self.call('submit',records=rows);self.assertEqual(len(r['records']),15)
  self.assertEqual(r['records'][-1]['children']['dependencies'][0]['depends_on_id'],r['records'][-2]['id'])
  self.assertEqual(r['records'][1]['children']['plan_items'][0]['plan_id'],r['records'][0]['id'])
 def test_amend_preserves_fields_and_noop(self):
  p=self.call('submit',records=[self.plan()])['records'][0];target={k:p[k] for k in ('kind','id','revision')}
  r=self.call('amend',changes=[{'target':target,'set_fields':{'design_body':'Changed'}}])['records'][0]
  self.assertEqual(r['fields']['rollback_body'],'Revert');self.assertEqual(r['children'],p['children'])
  with self.assertRaises(CoreError):self.call('amend',changes=[{'target':target,'set_fields':{'title':'stale'}}])
  target['revision']=r['revision'];r=self.call('amend',changes=[{'target':target}])['records'][0];self.assertEqual(r['outcome'],'unchanged')
 def test_atomic_rollback_and_error_location(self):
  rows=[self.plan(),{'client_ref':'bad','kind':'goal','fields':{}}]
  before=self.f.db.connection.execute('SELECT count(*) FROM plans').fetchone()[0]
  with self.assertRaises(CoreError) as e:self.call('submit',records=rows)
  self.assertEqual(e.exception.details['input_path'],'records[1]');self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM plans').fetchone()[0],before)
 def test_result_fail_is_not_automatically_incident_and_now_atomic(self):
  snap=self.f.call('observation.record',{'goal_id':self.f.goal,'paths':[{'source_id':'main','relative_path':'a.py','access':'read'}],'summary':'scope'})['snapshot_id']
  ev={'surface':'unit','result':'FAIL','summary':'test failed','method':'test'}
  self.call('result',snapshot_id=snap,evidence=ev)
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM failure_occurrences').fetchone()[0],0)
  r=self.call('result',snapshot_id=snap,evidence=ev,failure={'classification':'product','expected':'expected behavior','conditions':'race'},now={'statement':'Known defect','source_id':'main'})
  self.assertEqual(r['failure']['body']['expected'],'expected behavior');self.assertEqual(r['failure']['occurrences'][0]['classification'],'product');self.assertIn('now',r)
 def test_retry_and_changed_key(self):
  actor=self.f.actor();c=self.f.command('authoring.submit',{'base':self.base,'records':[self.plan()]},key='retry')
  a=self.f.core.execute(c,actor,self.f.ctx);self.assertEqual(a,self.f.core.execute(c,actor,self.f.ctx))
  c['payload']['records'][0]['fields']['title']='different'
  with self.assertRaises(CoreError):self.f.core.execute(c,actor,self.f.ctx)
 def test_amend_rolls_back_and_reports_dependents_without_rewriting(self):
  p=self.call('submit',records=[self.plan()])['records'][0]
  w=self.f.work(plans=[{'plan_id':p['id'],'plan_revision':1,'plan_item_id':'step','rationale':'design'}])
  target={k:p[k] for k in ('kind','id','revision')}
  with self.assertRaises(CoreError):
   self.call('amend',changes=[{'target':target,'set_fields':{'title':'Changed'}},{'target':{'kind':'plan','id':'missing','revision':1}}])
  self.assertEqual(self.f.core.query('record',target,self.f.actor())['data']['current_revision'],1)
  saved=self.call('amend',changes=[{'target':target,'set_fields':{'title':'Changed'}}])['records'][0]
  self.assertIn({'kind':'work_item','id':w['id'],'revision':1},saved['affected_records'])
  self.assertEqual(self.f.db.connection.execute('SELECT current_revision FROM work_items WHERE id=?',(w['id'],)).fetchone()[0],1)
 def test_child_upsert_remove_preserve_position(self):
  item=self.plan();item['children']['items'][0]['position']=7
  p=self.call('submit',records=[item])['records'][0];target={k:p[k] for k in ('kind','id','revision')}
  row=dict(item['children']['items'][0]);row.pop('position');row['design_body']='Revised'
  p=self.call('amend',changes=[{'target':target,'upsert_items':{'items':[row,{'item_id':'retained','title':'Next','design_body':'Another step','verification_body':'Test'}]}}])['records'][0]
  self.assertEqual(p['children']['items'][0]['position'],7)
  target['revision']=2
  p=self.call('amend',changes=[{'target':target,'remove_items':{'items':[{'item_id':'step'}]}}])['records'][0]
  self.assertEqual([r['item_id'] for r in p['children']['items']],['retained'])
 def test_failed_now_rolls_back_evidence(self):
  snap=self.f.call('observation.record',{'goal_id':self.f.goal,'paths':[{'source_id':'main','relative_path':'a.py','access':'read'}],'summary':'scope'})['snapshot_id']
  before=self.f.db.connection.execute('SELECT count(*) FROM evidence').fetchone()[0]
  with self.assertRaises(CoreError):
   self.call('result',snapshot_id=snap,evidence={'surface':'unit','result':'NOT_RUN','summary':'Skipped','method':'none'},now={'statement':'Cannot claim this','source_id':'main'})
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM evidence').fetchone()[0],before)
 def test_cli_one_process_and_schema_contract(self):
  import subprocess,json,sys
  from pathlib import Path
  from scripts.generate_core_schema import contract
  from jsonschema import validate
  payload={'base':self.base,'records':[self.plan()]}
  validate(self.f.command('authoring.submit',payload),contract())
  proc=subprocess.run([sys.executable,'-m','skip_core.cli','--db',str(self.f.db.path),'--project','project','--workspace',str(self.f.root),'--receipt-scope','authoring-test','submit','--submission-id','one-call'],input=json.dumps(payload),text=True,capture_output=True,cwd=Path(__file__).resolve().parents[2])
  self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
  self.assertEqual(len(json.loads(proc.stdout)['data']['records']),1)
 def test_two_connections_cannot_overwrite_same_revision(self):
  from concurrent.futures import ThreadPoolExecutor
  from skip_core.db import Database
  from skip_core.service import Core
  p=self.call('submit',records=[self.plan()])['records'][0];target={k:p[k] for k in ('kind','id','revision')}
  def write(title):
   with Database(self.f.db.path) as db:
    try:
     Core(db).execute(self.f.command('authoring.amend',{'base':self.base,'changes':[{'target':target,'set_fields':{'title':title}}]}),self.f.actor())
     return 'ok'
    except CoreError as e:return e.code
  with ThreadPoolExecutor(2) as pool:results=list(pool.map(write,['first','second']))
  self.assertCountEqual(results,['ok','STALE'])
 def test_significant_failure_recovery_preserves_original(self):
  snap=self.f.call('observation.record',{'goal_id':self.f.goal,'paths':[{'source_id':'main','relative_path':'a.py','access':'read'}],'summary':'scope'})['snapshot_id']
  ev={'surface':'unit','result':'FAIL','summary':'Race','method':'test'}
  first=self.call('result',snapshot_id=snap,evidence=ev,failure={'classification':'product'})
  ev['result']='PASS'
  recovered=self.call('result',snapshot_id=snap,evidence=ev,failure={'classification':'product','case_id':first['failure']['id'],'expected':'One winner','conditions':'Two requests','action':'Lock before checking'})
  self.assertIn('attempt',recovered);self.assertEqual(recovered['failure']['body']['conditions'],'Two requests')
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM failure_occurrences').fetchone()[0],1)
  self.assertEqual(self.f.db.connection.execute('SELECT result FROM evidence WHERE id=?',(first['evidence']['evidence_id'],)).fetchone()[0],'FAIL')
 def test_invalid_alias_and_child_constraint_are_located(self):
  plan=self.plan();plan['children']['requirements']=[{'requirement_id':'$later','rationale':'forward'}]
  with self.assertRaises(CoreError) as e:self.call('submit',records=[plan])
  self.assertEqual(e.exception.details['input_path'],'records[0]')
  plan=self.plan();plan['children']['items']=[]
  with self.assertRaises(CoreError) as e:self.call('submit',records=[plan])
  self.assertIn('aggregate needs children',e.exception.details['constraint'])
 def test_selection_link_and_cross_goal_rejected(self):
  decision=self.call('submit',records=[{'client_ref':'d','kind':'decision','fields':{'question':'Choose','rationale':'Policy','risk_summary':'Limited'},'children':{'options':[{'label':'Yes','description':'Proceed','consequences':'Change','recommended':1},{'label':'No','description':'Stop','consequences':'None','recommended':0}]}}])['records'][0]
  selection=self.f.call('decision.select',{'decision_id':decision['id'],'revision':1,'option_id':decision['children']['options'][0]['option_id']},True)
  plan=self.plan();plan['children']['selections']=[{'selection_id':selection['selection_id'],'rationale':'Chosen'}]
  self.call('submit',records=[plan])
  self.f.request()
  with self.assertRaises(CoreError):
   self.f.call('authoring.submit',{'base':{'goal_id':self.f.goal,'request_id':self.f.request_id},'records':[plan]})
 def test_incomplete_receipt_is_explicit(self):
  p=self.plan();p['fields'].update(design_body='d'*60000,alternatives_body='a'*60000,rollback_body='r'*60000)
  r=self.call('submit',records=[p])
  self.assertTrue(r['committed']);self.assertFalse(r['complete'])
  self.assertIn('digest',r['records'][0]);self.assertNotIn('fields',r['records'][0])
