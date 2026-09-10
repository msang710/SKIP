import unittest
from unittest.mock import patch
from tests.core.helpers import Fixture
from adapters.codex.entry import run

class DecisionContextTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture();self.addCleanup(self.f.close);self.f.request()
        self.d=self.f.publish('decision',{'question':'Dinner','rationale':'Choose','risk_summary':'Preference'}, {'options':[
            {'option_id':v,'label':label,'description':label,'consequences':label,'recommended':0,'position':i}
            for i,(v,label) in enumerate([('a','Soup'),('b','Rice')])]})
    def listing(self):
        return self.f.core.query('record.list',{'goal_id':self.f.goal,'kind':'decision'},self.f.actor())['data']['items'][0]
    def test_unselected_list(self):
        self.assertEqual(self.listing()['selection_state'],'unselected')
        self.assertIsNone(self.listing()['selected_option'])
    def context(self,budget=18000):
        return self.f.core.query('context',{'goal_id':self.f.goal,'stage':'implementation','budget':budget},self.f.actor(),self.f.ctx)['data']
    def select(self,option):
        return self.f.call('decision.select',{'decision_id':self.d['id'],'revision':self.d['revision'],'option_id':option},True)
    def test_choice_changes_visible_in_all_read_paths(self):
        for option in ('a','b'):
            self.select(option)
            self.assertEqual(self.listing()['selected_option']['option_id'],option)
            self.assertEqual(self.listing()['selection_state'],'selected')
            context=self.context()
            decision=next(r for r in context['records'] if r['kind']=='decision')
            self.assertEqual(decision['selection']['option_id'],option)
            self.assertEqual(decision['selected_option']['option_id'],option)
            self.assertEqual(decision['selection_state'],'selected')
            record=self.f.core.query('record',{'kind':'decision','id':self.d['id']},self.f.actor())['data']
            inbox=self.f.core.query('inbox',{'goal_id':self.f.goal},self.f.actor())['data']['items'][0]
            self.assertEqual(record['selection'],decision['selection']);self.assertEqual(inbox['selection'],decision['selection'])
        small=self.context(1024)
        self.assertFalse(small['complete']);self.assertTrue(small['required_expansions'])
    def test_changed_decision_does_not_reuse_old_choice(self):
        self.select('a')
        self.f.call('record.propose_revision',{'kind':'decision','id':self.d['id'],'goal_id':self.f.goal,'request_id':self.f.request_id,
            'expected_revision':1,'fields':{**self.d['fields'],'question':'Different dinner'},'children':self.d['children']})
        decision=next(r for r in self.context()['records'] if r['kind']=='decision')
        self.assertIsNone(decision['selection']);self.assertIsNone(decision['selected_option']);self.assertEqual(decision['selection_state'],'stale')
        self.assertEqual(self.listing()['selection_state'],'stale');self.assertIsNone(self.listing()['selected_option'])
    def test_codex_answer_with_explicit_goal_reads_choice(self):
        self.select('b')
        with patch('adapters.codex.entry.current_user',return_value={'id':'actual-turn','text':'어떤 메뉴 골랐어?'}):
            result=run(self.f.root,self.f.root,'thread',self.f.root/'private'/'skip.db',project_id='project',goal_id=self.f.goal)
        decision=next(r for r in result['data']['context']['records'] if r['kind']=='decision')
        self.assertEqual(decision['selected_option']['label'],'Rice')

    def test_current_turn_returns_validated_choice(self):
        self.select('b');self.f.work();self.f.ctx.can_continue=True
        result=self.f.call('execution.begin_current',self.f.prepare,True)
        self.assertEqual(result['decision_basis'][0]['selection']['option_id'],'b')
        self.assertEqual(result['decision_basis'][0]['decision']['id'],self.d['id'])

    def test_revoked_choice_is_not_exposed_as_active(self):
        self.select('b')
        # Seed a revoked fixture; no revocation command is exposed to agents.
        self.f.db.connection.execute("INSERT INTO selection_revocations SELECT project_id,id,interaction_id,event_id,'fixture revocation',created_at FROM selections")
        decision=next(r for r in self.context()['records'] if r['kind']=='decision')
        self.assertEqual(decision['selection_state'],'revoked')
        self.assertEqual(self.listing()['selection_state'],'revoked');self.assertIsNone(self.listing()['selected_option'])
        self.assertIsNone(decision['selection']);self.assertIsNone(decision['selected_option'])
