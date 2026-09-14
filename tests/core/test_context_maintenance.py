import unittest
from unittest.mock import patch
from tests.core.helpers import Fixture
from skip_core.errors import CoreError

class PolicyTests(unittest.TestCase):
 def test_default_content_is_in_digest(self):
  from skip_core.policy import DEFAULT_RULES
  f=Fixture();self.addCleanup(f.close);f.core.project='project';before=f.core.policy_digest()
  with patch.dict(DEFAULT_RULES,{'C-011':'Changed maintenance rule'}):self.assertNotEqual(before,f.core.policy_digest())
 def test_setting_accepts_new_rule_and_rejects_unknown(self):
  f=Fixture();self.addCleanup(f.close)
  body={'disabled_default_rule_ids':['C-011'],'custom_rules':[]}
  f.call('settings.update',{'scope':'project','expected_revision':0,'body':body},True)
  self.assertNotIn('C-011',f.core.query('context',{'goal_id':f.request()['goal']['id'],'stage':'restore'},f.actor(),f.ctx)['data']['policy']['defaults'])
  with self.assertRaises(CoreError):f.call('settings.update',{'scope':'project','expected_revision':1,'body':{'disabled_default_rule_ids':['C-999'],'custom_rules':[]}},True)

class OriginalRuleTests(unittest.TestCase):
 def test_exact_approved_rule(self):
  from pathlib import Path
  import hashlib
  text=(Path(__file__).resolve().parents[2]/'references/context-maintenance.md').read_text().removesuffix('\n')
  self.assertEqual(hashlib.sha256(text.encode()).hexdigest(),'fc809b80133efcac00427397f250edf2085d81e7f170916d6a8c143884348c77')
