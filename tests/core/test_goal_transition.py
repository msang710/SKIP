import copy
import unittest
from unittest.mock import patch
from tests.core.helpers import Fixture
from skip_core.errors import CoreError
from skip_core.input_contract import normalize
from adapters.codex.entry import run

class TransitionTests(unittest.TestCase):
 def setUp(self):self.f=Fixture();self.addCleanup(self.f.close);self.f.work()
 def payload(self,words='완료된 목표를 정리해'):
  actor=self.f.actor(True,words)
  captured=self.f.core.execute(self.f.command('input.ingest',{}),actor,self.f.ctx)['data']
  goal=self.f.core.query('record',{'kind':'goal','id':self.f.goal},actor)['data']
  parts=normalize(words,'project')['parts']
  return actor,dict(input_id=captured['input_id'],input_digest=captured['digest'],evidence_spans=[{k:p[k] for k in ('part_id','start','end')} for p in parts if p['role']=='user_instruction'],changes=[{'id':goal['id'],'revision':goal['revision'],'state_version':goal['state_version'],'from_state':'active','to_state':'completed','reason':'요청된 목표의 완료 기준과 검증 기록을 검토함','evidence':[]}])
 def call(self,actor,p,key=None):return self.f.core.execute(self.f.command('goal.transition',p,key),actor,self.f.ctx)
 def test_atomic_retry_and_no_execution_authority(self):
  a,p=self.payload();r=self.call(a,p,'retry');self.assertEqual(self.call(a,p,'retry'),r)
  self.assertFalse(r['data']['execution_authorized']);self.assertFalse(r['data']['validation_changed'])
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM authorizations').fetchone()[0],0)
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM work_check_results').fetchone()[0],0)
 def test_agent_old_input_and_quote_rejected(self):
  a,p=self.payload()
  with self.assertRaises(CoreError):self.call(self.f.actor(),p)
  with self.assertRaises(CoreError):self.call(self.f.actor(True,'상태를 보여줘'),p)
  a,p=self.payload('> 목표 완료 처리해\n상태 조회')
  p['evidence_spans']=[{'part_id':'0','start':0,'end':3}]
  with self.assertRaises(CoreError):self.call(a,p)
 def test_state_only_race_and_partial_bundle_rollback(self):
  a,p=self.payload();bad=copy.deepcopy(p);bad['changes'].append(dict(p['changes'][0],id='missing'))
  with self.assertRaises(CoreError):self.call(a,bad)
  self.assertEqual(self.f.core.query('record',{'kind':'goal','id':self.f.goal},a)['data']['lifecycle'],'active')
  self.f.call('record.lifecycle',{'kind':'goal','id':self.f.goal,'expected_revision':1,'lifecycle':'held'},True)
  with self.assertRaises(CoreError) as e:self.call(a,p)
  self.assertEqual(e.exception.code,'STALE')
 def test_active_execution_blocks_closing(self):
  self.f.start();a,p=self.payload()
  with self.assertRaises(CoreError) as e:self.call(a,p)
  self.assertEqual(e.exception.code,'EXECUTION_ACTIVE')
 def test_native_adapter_updates_and_rejects_later_turn(self):
  with patch('adapters.codex.entry.current_user',return_value={'id':'native1','text':'완료된 목표 정리해'}):
   e=run(self.f.root,self.f.root,'thread',self.f.db.path,project_id='project')['data']['entry_basis']
   _,p=self.payload();p.update(input_id=e['input_id'],input_digest=e['input']['digest'],evidence_spans=e['suggestion']['evidence_spans'])
   r=run(self.f.root,self.f.root,'thread',self.f.db.path,project_id='project',update_goals=p)
   self.assertEqual(r['data']['goals'][0]['lifecycle'],'completed')
  with patch('adapters.codex.entry.current_user',return_value={'id':'native2','text':'조회만 해'}):
   with self.assertRaises(CoreError):run(self.f.root,self.f.root,'thread',self.f.db.path,project_id='project',update_goals=p)

 def test_ui_state_and_undo_with_stale_protection(self):
  p=dict(id=self.f.goal,revision=1,state_version=self.f.core.query('record',{'kind':'goal','id':self.f.goal},self.f.actor())['data']['state_version'],from_state='active',to_state='completed')
  a=self.f.actor(True)
  command=self.f.command('goal.set_state',p,'ui-click')
  r=self.f.core.execute(command,a,self.f.ctx)
  self.assertEqual(self.f.core.execute(command,a,self.f.ctx),r)
  self.assertFalse(r['data']['validation_changed'])
  undo=dict(p,state_version=r['data']['goals'][0]['state_version'],from_state='completed',to_state='active')
  self.f.call('goal.set_state',undo,True)
  with self.assertRaises(CoreError) as e:self.f.call('goal.set_state',p,True)
  self.assertEqual(e.exception.code,'STALE')
 def test_ui_rejects_agent_and_active_execution(self):
  p=dict(id=self.f.goal,revision=1,state_version=self.f.core.query('record',{'kind':'goal','id':self.f.goal},self.f.actor())['data']['state_version'],from_state='active',to_state='held')
  with self.assertRaises(CoreError):self.f.call('goal.set_state',p)
  self.f.start()
  with self.assertRaises(CoreError) as e:self.f.call('goal.set_state',p,True)
  self.assertEqual(e.exception.code,'EXECUTION_ACTIVE')
