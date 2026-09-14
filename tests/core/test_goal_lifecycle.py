import unittest
from tests.core.helpers import Fixture
from skip_core.errors import CoreError

class GoalLifecycleTests(unittest.TestCase):
    def setUp(self):self.f=Fixture();self.addCleanup(self.f.close);self.f.work()
    def state(self,value):return self.f.call('record.lifecycle',{'kind':'goal','id':self.f.goal,'expected_revision':1,'lifecycle':value},True)
    def query(self,name,p=None):return self.f.core.query(name,p or {},self.f.actor())['data']
    def test_past_goals_are_listed_but_not_current_and_stay_readable(self):
        for state in ('completed','archived'):
            self.state(state)
            self.assertEqual(self.query('goal.list')['goals'][0]['lifecycle'],state)
            self.assertEqual(self.query('status')['goals'],[])
            self.assertEqual(self.query('status',{'goal_id':self.f.goal})['goals'][0]['id'],self.f.goal)
            self.assertEqual(self.query('context',{'goal_id':self.f.goal,'stage':'restore'})['records'][0]['id'],self.f.goal)
            with self.assertRaises(CoreError):self.f.start()
        self.state('active');self.assertEqual(len(self.query('status')['goals']),1)
    def test_held_stays_current_and_agent_cannot_declare_completion(self):
        self.state('held');self.assertEqual(self.query('status')['goals'][0]['lifecycle'],'held')
        with self.assertRaises(CoreError):self.f.call('record.lifecycle',{'kind':'goal','id':self.f.goal,'expected_revision':1,'lifecycle':'completed'})
    def test_pagination_and_completed_not_supported_for_other_records(self):
        for _ in range(3):self.f.request()
        first=self.query('goal.list',{'limit':2});second=self.query('goal.list',{'limit':2,'cursor':first['next_cursor']})
        self.assertEqual(len({g['id'] for g in first['goals']+second['goals']}),4)
        with self.assertRaises(CoreError):self.f.call('record.lifecycle',{'kind':'work_item','id':self.f.w['id'],'expected_revision':1,'lifecycle':'completed'},True)
