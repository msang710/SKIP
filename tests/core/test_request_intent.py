import unittest
from unittest.mock import patch
from tests.core import test_semantic_execution as harness
from skip_core.errors import CoreError
from skip_core.request_intent import resolve

class RequestIntentTests(unittest.TestCase):
 def setUp(self):
  self.t=harness.SemanticExecutionTests();self.t.setUp();self.addCleanup(self.t.doCleanups);self.f=self.t.f
 def test_request_cancel_updates_same_input_head(self):
  entry,body=self.t.save();x=self.t.begin()['data']['execution_id'];self.t.run_entry(finish=x)
  rid=self.f.db.connection.execute('SELECT a.request_id FROM executions x JOIN authorizations a ON a.project_id=x.project_id AND a.id=x.authorization_id WHERE x.id=?',(x,)).fetchone()[0]
  body.update(acts=['cancel']);self.f.call('intent.propose',dict(request_id=rid,expected_revision=1,body=body))
  a=self.f.core.query('entry.inspect',{'request_id':rid},self.f.actor())['data']['interpretation']
  b=self.f.core.query('entry.inspect',{'input_id':entry['input_id']},self.f.actor())['data']['interpretation']
  self.assertEqual(a,b);self.assertEqual(a['body']['acts'],['cancel'])
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM intent_interpretations WHERE input_id=?',(entry['input_id'],)).fetchone()[0],0)
  with self.assertRaises(CoreError):self.t.begin()
 def test_multiple_explicit_work_targets_each_allowed(self):
  first=self.f.w;first_prepare=self.f.prepare.copy();self.f.work();second=self.f.w;second_prepare=self.f.prepare.copy()
  self.t.save(targets=[{'kind':'work_item','id':r['id'],'revision':1} for r in (first,second)])
  for p in (first_prepare,second_prepare):
   self.f.prepare=p;x=self.t.begin()['data'];self.assertEqual(x['authorization'],'ALLOW');self.t.run_entry(finish=x['execution_id'])
 def plan(self):
  return self.f.publish('plan',dict(title='Selected plan',design_body='Only chosen work',scope_description='Local',alternatives_body='None',rollback_body='Revert'),{'items':[dict(item_id='step',title='Chosen step',design_body='Only this',verification_body='Check',position=0)]})
 def test_selected_plan_requires_real_work_relationship(self):
  p=self.plan();self.t.save(targets=[{'kind':'plan','id':p['id'],'revision':1}])
  with self.assertRaises(CoreError):self.t.begin()
  self.f.work(plans=[dict(plan_id=p['id'],plan_revision=1,plan_item_id='step',rationale='Chosen plan')])
  self.assertEqual(self.t.begin()['data']['authorization'],'ALLOW')
 def test_saved_implementation_can_resume_before_first_execution(self):
  self.t.save();self.t.user={'id':'chosen','text':'선택했어 계속해'};self.t.save(acts=['resume'])
  self.assertEqual(self.t.begin()['data']['authorization'],'ALLOW')
 def test_saved_stop_is_not_skipped_for_an_older_implementation(self):
  self.t.save();self.t.user={'id':'stop','text':'중지해'};self.t.save(acts=['cancel'])
  self.t.user={'id':'later','text':'계속해'};self.t.save(acts=['resume'])
  with self.assertRaises(CoreError):self.t.begin()
 def test_proposal_approval_survives_continuation(self):
  c=self.f.db.connection;snapshot=c.execute('SELECT s.digest FROM risk_assessments r JOIN snapshots s ON s.project_id=r.project_id AND s.id=r.snapshot_id WHERE r.id=?',(self.f.prepare['goal_risk_id'],)).fetchone()[0]
  p=self.f.call('action.propose',dict(request_id=self.f.request_id,body=dict(action='implement',target={'kind':'work_item','id':self.f.w['id'],'revision':1},scope_digest=snapshot,constraints=[])))
  self.t.user={'id':'approval','text':'승인'}
  with patch('adapters.codex.entry.proposal_reply',return_value=(p['id'],1)):self.t.run_entry(goal_id=self.f.goal)
  x=self.t.begin()['data']['execution_id'];self.t.run_entry(finish=x)
  self.t.user={'id':'resume-proposal','text':'계속해'};self.t.save(acts=['resume'])
  self.assertEqual(self.t.begin()['data']['authorization'],'ALLOW')
 def test_old_and_new_cas_routes_share_one_revision(self):
  e,body=self.t.save();body.update(acts=['answer'])
  self.f.call('intent.propose',dict(input_id=e['input_id'],input_digest=e['input']['digest'],expected_revision=1,body=body))
  with self.assertRaises(CoreError):self.f.call('intent.propose',dict(input_id=e['input_id'],input_digest=e['input']['digest'],expected_revision=1,body=body))
 def test_delivery_rechecks_latest_stop(self):
  from skip_core.delivery import Delivery
  actor=self.f.actor(True,words='이제 구현해')
  rid=self.f.core.execute(self.f.command('request.submit',dict(text=actor.user_text,operation='implement',goal_id=self.f.goal)),actor,self.f.ctx)['data']['request_id']
  x=self.f.core.execute(self.f.command('execution.prepare',self.f.prepare),actor,self.f.ctx)['data']['execution_id']
  entry=self.f.core.query('entry.inspect',{'request_id':rid},self.f.actor())['data'];body=entry['interpretation']['body'];body['acts']=['cancel']
  self.f.call('intent.propose',dict(request_id=rid,expected_revision=entry['interpretation']['revision'],body=body))
  with self.assertRaises(CoreError):Delivery(self.f.core,self.f.ctx).claim(x)
 def test_semantic_change_between_precheck_and_begin_is_rejected(self):
  from skip_core.service import Core
  e,body=self.t.save();original=Core.execute;changed=False
  def execute(core,command,principal,context=None):
   nonlocal changed
   if command['command']=='execution.begin_current' and not changed:
    changed=True;body['acts']=['cancel']
    self.f.call('intent.propose',dict(input_id=e['input_id'],input_digest=e['input']['digest'],expected_revision=1,body=body))
   return original(core,command,principal,context)
  with patch.object(Core,'execute',execute):
   with self.assertRaises(CoreError):self.t.begin()
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM executions').fetchone()[0],0)
 def test_conflicting_legacy_heads_require_reconciliation(self):
  from skip_core.common import digest,encoded
  e,body=self.t.save();x=self.t.begin()['data']['execution_id'];self.t.run_entry(finish=x)
  c=self.f.db.connection;rid=c.execute('SELECT a.request_id FROM executions x JOIN authorizations a ON a.project_id=x.project_id AND a.id=x.authorization_id WHERE x.id=?',(x,)).fetchone()[0]
  row=c.execute('SELECT * FROM input_intent_versions WHERE input_id=?',(e['input_id'],)).fetchone();body['acts']=['cancel']
  c.execute('INSERT INTO intent_interpretations (project_id,request_id,revision,input_id,body_json,digest,event_id) VALUES (?,?,?,?,?,?,?)',('project',rid,1,e['input_id'],encoded(body),digest(body),row['event_id']))
  with self.assertRaises(CoreError) as error:self.t.begin()
  self.assertEqual(error.exception.code,'CONFLICT')
  self.f.call('intent.propose',dict(request_id=rid,expected_revision=1,body=body))
  result=self.f.core.query('entry.inspect',{'request_id':rid},self.f.actor())['data']['interpretation'];self.assertEqual(result['body']['acts'],['cancel'])
 def test_later_request_in_another_conversation_cannot_supply_resume(self):
  self.t.save();self.t.user={'id':'other','text':'계속해'}
  with patch('adapters.codex.entry.current_user',return_value=self.t.user):
   from adapters.codex.entry import run
   e=run(self.f.root,self.f.root,'other-thread',self.f.db.path,project_id='project')['data']['entry_basis']
   body=dict(acts=['resume'],constraints=[],targets=[{'kind':'work_item','id':self.f.w['id'],'revision':1}],unresolved=[],evidence_spans=e['suggestion']['evidence_spans'])
   self.f.call('entry.submit',dict(input_id=e['input_id'],input_digest=e['input']['digest'],expected_revision=0,body=body,target={'mode':'none'},records=[]))
   with self.assertRaises(CoreError):run(self.f.root,self.f.root,'other-thread',self.f.db.path,project_id='project',begin=self.f.prepare)
 def test_later_native_proposal_binding_wins_over_earlier_answer(self):
  c=self.f.db.connection;snapshot=c.execute('SELECT s.digest FROM risk_assessments r JOIN snapshots s ON s.project_id=r.project_id AND s.id=r.snapshot_id WHERE r.id=?',(self.f.prepare['goal_risk_id'],)).fetchone()[0]
  p=self.f.call('action.propose',dict(request_id=self.f.request_id,body=dict(action='implement',target={'kind':'work_item','id':self.f.w['id'],'revision':1},scope_digest=snapshot,constraints=[])))
  self.t.user={'id':'approval-after-answer','text':'승인'}
  with patch('adapters.codex.entry.proposal_reply',return_value=None):self.t.save(acts=['answer'])
  with patch('adapters.codex.entry.proposal_reply',return_value=(p['id'],1)):self.t.run_entry(goal_id=self.f.goal)
  self.assertEqual(self.t.begin()['data']['authorization'],'ALLOW')
 def test_revoked_authorization_cannot_be_inherited(self):
  self.t.save();x=self.t.begin()['data']['execution_id'];self.t.run_entry(finish=x)
  c=self.f.db.connection
  c.execute("INSERT INTO authorization_revocations(project_id,authorization_id,interaction_id,event_id,reason,created_at) SELECT a.project_id,a.id,a.interaction_id,a.event_id,'revoked fixture',a.created_at FROM authorizations a JOIN executions x ON x.project_id=a.project_id AND x.authorization_id=a.id WHERE x.id=?",(x,))
  self.t.user={'id':'resume-revoked','text':'계속해'};self.t.save(acts=['resume'])
  with self.assertRaises(CoreError):self.t.begin()
