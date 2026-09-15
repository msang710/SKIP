import unittest
from tests.core.helpers import Fixture
from skip_core.delivery import Delivery
from skip_core.errors import CoreError

class ExecutionRequestTests(unittest.TestCase):
 def setUp(self):
  self.f=Fixture();self.addCleanup(self.f.close)
  r=self.f.call('request.submit',{'text':'구현하지 말고 계획만 작성해','operation':'plan'},True,words='구현하지 말고 계획만 작성해')
  self.f.request_id=r['request_id'];self.f.goal=r['goal']['id'];self.f.work()
 def test_delivery_uses_execution_request_without_rewriting_work(self):
  before=self.f.core.query('record',{'kind':'work_item','id':self.f.w['id']},self.f.actor())['data']
  prepared=self.f.call('execution.prepare',self.f.prepare,True,words='이제 구현해')
  x=self.f.core.one('executions',prepared['execution_id']);a=self.f.core.one('authorizations',x['authorization_id'])
  self.assertNotEqual(a['request_id'],self.f.request_id)
  claim=Delivery(self.f.core,self.f.ctx).claim(x['id']);self.assertEqual(claim['execution_id'],x['id'])
  after=self.f.core.query('record',{'kind':'work_item','id':self.f.w['id']},self.f.actor())['data']
  self.assertEqual(before,after)
 def test_current_request_prohibition_still_applies(self):
  actor=self.f.actor(True,words='구현하지 말고 계획만 작성해')
  self.f.core.execute(self.f.command('request.submit',{'text':actor.user_text,'operation':'plan','goal_id':self.f.goal}),actor,self.f.ctx)
  self.f.ctx.can_continue=True
  with self.assertRaises(CoreError):self.f.core.execute(self.f.command('execution.begin_current',self.f.prepare),actor,self.f.ctx)
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM executions').fetchone()[0],0)
 def test_failed_preparation_rolls_back_new_execution_request(self):
  before=self.f.db.connection.execute('SELECT count(*) FROM requests').fetchone()[0]
  with self.assertRaises(CoreError):self.f.call('execution.prepare',{**self.f.prepare,'goal_risk_id':'missing'},True,words='이제 구현해')
  self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM requests').fetchone()[0],before)
