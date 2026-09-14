import unittest
from tests.core.helpers import Fixture
from skip_core.errors import CoreError
from skip_core.authority import ExecutionContext

class ProfileTests(unittest.TestCase):
 def setUp(self):
  self.f=Fixture();self.addCleanup(self.f.close)
 def query(self,**p):return self.f.core.query('project.profile',p,self.f.actor(),self.f.ctx)['data']
 def connect(self,session='s',namespace='host'):
  self.f.ctx.caller_verified=True
  self.f.ctx.participant={'namespace':namespace,'agent_id':None,'session_id':session}
  self.f.ctx.participant_touched=False
 def save(self,base=None,body='Purpose'):
  return self.f.call('project.profile.save',{'expected_revision':base,'tagline':'Intro','body_markdown':body},human=True)
 def test_optional_and_agent_cannot_accept(self):
  self.assertFalse(self.query()['metadata']['available'])
  with self.assertRaises(CoreError):self.f.call('project.profile.save',{'expected_revision':None,'tagline':'x','body_markdown':'x'})
  p=self.f.call('project.profile.propose',{'expected_revision':None,'tagline':'x','body_markdown':'x'})
  self.assertIsNone(self.query()['profile'])
  self.assertEqual(len(self.query(include_proposals=True)['proposals']),1)
  self.f.call('project.profile.accept',{'expected_revision':None,'revision':p['revision'],'digest':p['digest']},human=True)
  self.assertEqual(self.query()['profile']['tagline'],'x')
 def test_same_session_reconnect_new_session_and_namespace(self):
  self.connect();self.save();self.query()
  self.connect();self.assertEqual(self.query()['metadata']['change_state'],'unchanged')
  self.connect('new');self.assertEqual(self.query()['metadata']['change_state'],'unread')
  self.connect('s','other');self.query()
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM project_participations').fetchone()[0],3)
 def test_metadata_does_not_inject_or_mark_read(self):
  self.connect();self.save();self.f.request()
  for name,p in [('status',{}),('context',{'goal_id':self.f.goal,'stage':'restore'})]:
   data=self.f.core.query(name,p,self.f.actor(),self.f.ctx)['data']
   self.assertEqual(data['project_profile']['change_state'],'unread')
   self.assertNotIn('body_markdown',data['project_profile'])
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM project_profile_reads').fetchone()[0],0)
 def test_partial_ui_and_failed_reads_do_not_count(self):
  self.connect();self.save(body='long '*1000)
  self.assertFalse(self.query(budget=1024)['complete'])
  with self.assertRaises(CoreError):self.query(revision=999)
  self.query(include_proposals=True)
  self.f.ctx.participant_route='ui';self.query()
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM project_profile_reads').fetchone()[0],0)
  self.f.ctx.participant_route='agent';self.query();self.query()
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM project_profile_reads').fetchone()[0],2)
 def test_changed_cas_and_old_revision_reread(self):
  self.connect();first=self.save();self.query()
  self.save(first['revision'],'new')
  self.assertEqual(self.query()['metadata']['change_state'],'changed')
  with self.assertRaises(CoreError):self.save(first['revision'],'outdated')
  self.assertEqual(self.query(revision=first['revision'])['profile']['body_markdown'],'Purpose')
 def test_replay_and_noop(self):
  actor=self.f.actor(True);cmd=self.f.command('project.profile.save',{'expected_revision':None,'tagline':'x','body_markdown':'y'},'same')
  a=self.f.core.execute(cmd,actor,self.f.ctx);b=self.f.core.execute(cmd,actor,self.f.ctx)
  self.assertEqual(a,b)
  r=self.f.call('project.profile.save',{'expected_revision':1,'tagline':'x','body_markdown':'y'},human=True)
  self.assertTrue(r['unchanged'])
 def test_change_event_and_project_foreign_key(self):
  import sqlite3
  before=self.f.core.query('changes',{},self.f.actor())['sequence'];self.save()
  feed=self.f.core.query('changes',{'since':before},self.f.actor())['data']
  self.assertEqual(feed['events'][0]['kind'],'project.profile.save')
  with self.assertRaises(sqlite3.IntegrityError):self.f.db.connection.execute("INSERT INTO project_profiles VALUES ('another',1)")
 def test_candidate_upgrade_preserves_all_existing_tables(self):
  from unittest.mock import patch
  from skip_core.db import Database
  from skip_core.upgrade import candidate
  original=Database.migrations
  with patch.object(Database,'migrations',side_effect=lambda:original()[:6]), patch('skip_core.record_state.metadata',return_value=None):
   old=Fixture();self.addCleanup(old.close);old.request();old.work()
   tables=[r[0] for r in old.db.connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name<>'schema_migrations'")]
   before={t:[tuple(r) for r in old.db.connection.execute('SELECT * FROM '+t)] for t in tables}
  target=old.root/'profile-candidate.db';result=candidate(old.db.path,target)
  self.assertFalse(result['activated'])
  self.assertEqual(old.db.connection.execute('SELECT max(version) FROM schema_migrations').fetchone()[0],6)
  with Database(target) as db:
   self.assertEqual(db.connection.execute('SELECT max(version) FROM schema_migrations').fetchone()[0],max(v for v,_,_ in Database.migrations()))
   for table,rows in before.items():self.assertEqual([tuple(r) for r in db.connection.execute('SELECT * FROM '+table)],rows,table)
   self.assertFalse(db.connection.execute('PRAGMA foreign_key_check').fetchall())
   self.assertEqual(db.connection.execute('SELECT count(*) FROM project_profiles').fetchone()[0],0)
 def test_unknown_identity_stays_unknown_and_stale_proposal_can_be_rejected(self):
  first=self.f.call('project.profile.propose',{'expected_revision':None,'tagline':'old','body_markdown':'candidate'})
  accepted=self.save()
  self.f.call('project.profile.reject',{'revision':first['revision'],'digest':first['digest'],'expected_revision':accepted['revision']},human=True)
  data=self.query(include_proposals=True)
  self.assertEqual(data['metadata']['change_state'],'unknown');self.assertFalse(data['proposals'])
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM project_profile_reads').fetchone()[0],0)
