import unittest
from tests.core.helpers import Fixture

class ChangeSignalTests(unittest.TestCase):
 def test_reads_do_not_advance_signal_but_other_connection_writes_do(self):
  from skip_core.db import Database
  from skip_core.service import Core
  f=Fixture();self.addCleanup(f.close);f.request()
  before=f.core.query('changes',{},f.actor())['sequence']
  self.assertEqual(f.core.query('changes',{},f.actor())['sequence'],before)
  with Database(f.db.path) as db:
   Core(db).execute(f.command('record.propose_revision',{'kind':'work_item','expected_revision':0,'request_id':f.request_id,'goal_id':f.goal,'fields':{'operation':'implement','title':'Other session','instruction_body':'Change','completion_definition':'Check','workflow_depth':'compact','request_id':f.request_id},'children':{'checks':[{'check_id':'check','description':'Test','surface':'unit','required':1}]}}),f.actor())
  after=f.core.query('changes',{},f.actor())
  self.assertGreater(after['sequence'],before)
  self.assertEqual(after['data']['sequence'],after['sequence'])
 def test_changes_group_atomic_records_and_mark_truncation(self):
  from tests.core.test_authoring import AuthoringTests
  f=Fixture();self.addCleanup(f.close);f.request()
  before=f.core.query('changes',{},f.actor())['sequence']
  first=AuthoringTests().plan();second=AuthoringTests().plan();second['client_ref']='second'
  saved=f.call('authoring.submit',{'base':{'goal_id':f.goal,'request_id':f.request_id},'records':[first,second]})
  feed=f.core.query('changes',{'since':before},f.actor())['data']
  self.assertTrue(feed['complete'])
  self.assertEqual(len(feed['events']),1)
  self.assertEqual({r['id'] for r in feed['events'][0]['records']},{r['id'] for r in saved['records']})
  limited=f.core.query('changes',{'since':0,'limit':1},f.actor())['data']
  self.assertFalse(limited['complete']);self.assertTrue(limited['resync_required'])
