import unittest
from unittest.mock import patch
from tests.core.helpers import Fixture
from skip_core.errors import CoreError
from adapters.codex.entry import run

class SemanticExecutionTests(unittest.TestCase):
 def setUp(self):
  self.f=Fixture();self.addCleanup(self.f.close);self.f.work()
  self.user={'id':'native-choice','text':'선택했어 계속해'}
  self.mock=patch('adapters.codex.entry.current_user',side_effect=lambda *a,**kw:self.user.copy());self.mock.start();self.addCleanup(self.mock.stop)
 def run_entry(self,**kw):return run(self.f.root,self.f.root,'thread',self.f.db.path,project_id='project',**kw)
 def save(self,acts=None,constraints=None,targets=None):
  entry=self.run_entry()['data']['entry_basis'];body=dict(acts=acts or ['implement'],constraints=constraints or [],targets=targets if targets is not None else [{'kind':'work_item','id':self.f.w['id'],'revision':1}],unresolved=[],evidence_spans=entry['suggestion']['evidence_spans'])
  result=self.f.call('entry.submit',dict(input_id=entry['input_id'],input_digest=entry['input']['digest'],expected_revision=0,body=body,target={'mode':'none'},records=[]))
  return entry,body
 def begin(self):return self.run_entry(begin=self.f.prepare)
 def test_compound_input_uses_semantics(self):
  self.save();self.assertEqual(self.begin()['data']['authorization'],'ALLOW')
 def test_even_keyword_without_saved_meaning_requests_interpretation(self):
  self.user['text']='구현해'
  with self.assertRaises(CoreError) as e:self.begin()
  self.assertEqual(e.exception.code,'INTERPRETATION_REQUIRED')
 def test_latest_saved_stop_overrides_earlier_implementation(self):
  entry,body=self.save();body.update(acts=['cancel'])
  self.f.call('intent.propose',dict(input_id=entry['input_id'],input_digest=entry['input']['digest'],expected_revision=1,body=body))
  with self.assertRaises(CoreError) as e:self.begin()
  self.assertEqual(e.exception.code,'USER_ACTION_REQUIRED')
 def test_current_prohibition_and_read_only_are_not_execution(self):
  self.save(acts=['resume'],constraints=['implement'])
  with self.assertRaises(CoreError):self.begin()
 def test_status_interpretation_does_not_inherit_implementation(self):
  self.save(acts=['answer'])
  with self.assertRaises(CoreError):self.begin()
 def test_later_input_cannot_reuse_previous_interpretation(self):
  self.save();self.user={'id':'next-user','text':'잠깐'}
  with self.assertRaises(CoreError) as e:self.begin()
  self.assertEqual(e.exception.code,'INTERPRETATION_REQUIRED')
 def test_resume_requires_original_native_request(self):
  self.save(acts=['resume'])
  with self.assertRaises(CoreError) as e:self.begin()
  self.assertEqual(e.exception.code,'INTERPRETATION_REQUIRED')
 def test_finish_is_reporting_but_cannot_cross_conversations(self):
  self.save();x=self.begin()['data']['execution_id'];self.user={'id':'stop','text':'그만해'}
  with self.assertRaises(CoreError):run(self.f.root,self.f.root,'other-thread',self.f.db.path,project_id='project',finish=x)
  self.assertEqual(self.run_entry(finish=x)['data']['state'],'finished')
 def test_no_target_is_not_blanket_execution_permission(self):
  self.save(targets=[])
  with self.assertRaises(CoreError) as e:self.begin()
  self.assertEqual(e.exception.code,'INTERPRETATION_REQUIRED')
