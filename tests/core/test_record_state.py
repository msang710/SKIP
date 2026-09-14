import unittest
from unittest.mock import patch
from skip_core.db import Database
from skip_core.errors import CoreError
from tests.core.helpers import Fixture

class RecordStateTests(unittest.TestCase):
 def setUp(self):self.f=Fixture();self.addCleanup(self.f.close);self.f.work()
 def record(self,r):return self.f.core.query('record',{'kind':r.get('kind','plan'),'id':r['id']},self.f.actor())['data']
 def plan(self,title='Design'):
  r=self.f.publish('plan',dict(title=title,design_body='Implementation',scope_description='Local',alternatives_body='Options',rollback_body='Revert'),{'items':[dict(item_id='i',title='Item',design_body='Body',verification_body='Test',position=0)]})
  return self.record(dict(r,kind='plan'))
 def state(self,r,to,**kw):
  return self.f.call('record.set_state',dict(kind=r['kind'],id=r['id'],revision=r['revision'],state_version=r['state_version'],from_state=r['lifecycle'],to_state=to,**kw),True)
 def test_rejection_context_history_and_restore(self):
  r=self.plan()
  with self.assertRaises(CoreError):self.state(r,'rejected',reason=' ')
  result=self.state(r,'rejected',reason='Does not meet the requirement')
  p=dict(goal_id=self.f.goal,stage='implementation')
  context=self.f.core.query('context',p,self.f.actor())['data']
  self.assertNotIn(r['id'],[x['id'] for x in context['records']])
  self.assertEqual(context['inactive_records'][0]['reason'],'Does not meet the requirement')
  for include,count in ((False,0),(True,1)):
   rows=self.f.core.query('record.list',{'kind':'plan','include_inactive':include},self.f.actor())['data']['items']
   self.assertEqual(len(rows),count)
  self.assertEqual(self.f.core.query('record',{'kind':'goal','id':self.f.goal},self.f.actor())['data']['lifecycle'],'active')
  restored=self.state(self.record(r),'active')
  self.assertEqual(restored['previous']['lifecycle'],'rejected')
  history=self.f.core.query('record.state_history',{'kind':'plan','id':r['id']},self.f.actor())['data']['items']
  self.assertEqual([x['to_state'] for x in history],['active','rejected'])
  with self.assertRaises(CoreError) as e:self.state(r,'held')
  self.assertEqual(e.exception.code,'STALE')
 def test_replacement_identity_scope_revision_and_undo(self):
  r=self.plan('Old');other=self.plan('New');ref={k:other[k] for k in ('kind','id','revision')}
  for bad in ({**ref,'id':r['id']},{**ref,'kind':'requirement'},{**ref,'revision':0}):
   with self.assertRaises(CoreError):self.state(r,'superseded',reason='New approach',replacement=bad)
  result=self.state(r,'superseded',reason='New approach',replacement=ref)
  self.assertEqual(result['state_change']['replacement'],ref)
  self.state(self.record(r),'archived')
  self.state(self.record(r),'superseded',reason='New approach',replacement=ref)
  self.state(self.record(other),'held')
  with self.assertRaises(CoreError):self.state(self.record(r),'superseded',reason='Unavailable',replacement=ref)
  self.assertFalse(result['validation_changed']);self.assertFalse(result['execution_authorized'])
 def test_inactive_referenced_design_blocks_execution_and_running_blocks_change(self):
  r=self.plan();self.f.work(plans=[dict(plan_id=r['id'],plan_revision=1,plan_item_id='i',rationale='Design basis')])
  self.state(r,'rejected',reason='Unsafe design')
  with self.assertRaises(CoreError):self.f.start()
  self.state(self.record(r),'active');self.f.start()
  with self.assertRaises(CoreError) as e:self.state(self.record(r),'held')
  self.assertEqual(e.exception.code,'EXECUTION_ACTIVE')
 def test_agent_cannot_change_and_all_document_kinds_accept_rejection(self):
  for r in [self.plan(),self.record(dict(self.f.w,kind='work_item')),self.record(dict(self.f.publish('requirement',dict(title='R',statement='Must',rationale='Why'),{'criteria':[dict(criterion_id='c',description='Test',given_text='Given',when_text='When',then_text='Then',required=1)]}),kind='requirement'))]:
   payload=dict(kind=r['kind'],id=r['id'],revision=r['revision'],state_version=r['state_version'],from_state=r['lifecycle'],to_state='rejected',reason='Review')
   with self.assertRaises(CoreError):self.f.call('record.set_state',payload)
   self.f.call('record.set_state',payload,True)

 def test_native_ui_ticket_retry_and_read_history(self):
  from skip_core.bridge import NativeBridge
  r=self.plan();bridge=NativeBridge(self.f.db.path);self.addCleanup(bridge.close)
  bridge.dispatch({'operation':'connect','project_id':'project','sources':{'main':str(self.f.root)},'identity':['paseo','workspace','ui']})
  cmd=self.f.command('record.set_state',dict(kind='plan',id=r['id'],revision=r['revision'],state_version=r['state_version'],from_state='active',to_state='rejected',reason='User review'))
  ticket=bridge.dispatch({'operation':'card','command':cmd})['ticket']
  event={'operation':'user','command':cmd,'ticket':ticket,'user_event':{'id':'click','text':'반려'}}
  value=bridge.dispatch(event)
  self.assertEqual(bridge.dispatch(event),value)
  history=bridge.dispatch({'operation':'query','query':'record.state_history','payload':{'kind':'plan','id':r['id']}})['data']['items']
  self.assertEqual(len(history),1);self.assertEqual(history[0]['reason'],'User review')
  with self.assertRaises(CoreError):bridge.dispatch({'operation':'agent','command':cmd})

 def test_replacement_in_another_goal_and_stale_target_are_rejected(self):
  r=self.plan();target=self.plan('Replacement');ref={k:target[k] for k in ('kind','id','revision')}
  self.state(target,'held')
  with self.assertRaises(CoreError):self.state(r,'superseded',reason='New',replacement=ref)
  self.f.request();other=self.plan('Another goal');ref={k:other[k] for k in ('kind','id','revision')}
  with self.assertRaises(CoreError) as e:self.state(r,'superseded',reason='Wrong goal',replacement=ref)
  self.assertEqual(e.exception.code,'PROJECT_MISMATCH')

class RecordStateMigrationTests(unittest.TestCase):
 def test_upgrade_preserves_rows_and_triggers(self):
  migrations=Database.migrations()
  with patch.object(Database,'migrations',return_value=[m for m in migrations if m[0]<10]),patch('skip_core.record_state.metadata',return_value=None):
   f=Fixture();self.addCleanup(f.close);f.work()
   # Include actual records, references, snapshots and user input in schema 9.
   c=f.db.connection
   tables=[r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'schema_migrations'")]
   before={t:sorted(tuple(r) for r in c.execute(f'SELECT * FROM {t}')) for t in tables}
   triggers={r[0]:r[1] for r in c.execute("SELECT name,sql FROM sqlite_master WHERE type IN ('trigger','index') AND sql IS NOT NULL")}
   f.db.close()
  upgraded=Database(f.db.path,create=True);self.addCleanup(upgraded.close)
  c=upgraded.connection
  for t,rows in before.items():self.assertEqual(sorted(tuple(r) for r in c.execute(f'SELECT * FROM {t}')),rows,t)
  for name,sql in triggers.items():self.assertEqual(c.execute('SELECT sql FROM sqlite_master WHERE name=?',(name,)).fetchone()[0],sql,name)
  self.assertEqual(c.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertEqual(c.execute('PRAGMA foreign_key_check').fetchall(),[])
