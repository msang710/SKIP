import unittest
from tests.core.helpers import Fixture
from skip_core.input_contract import normalize,classify
from skip_core.errors import CoreError

class EntryTests(unittest.TestCase):
    def setUp(self):self.f=Fixture();self.addCleanup(self.f.close)
    def request(self,words):
        actor=self.f.actor(True,words)
        self.f.core.execute(self.f.command('input.ingest',{}),actor,self.f.ctx)
        r=self.f.core.execute(self.f.command('request.submit',{'text':words,'operation':'plan'}),actor,self.f.ctx)['data']
        self.f.request_id=r['request_id'];self.f.goal=r['goal']['id']
        return r['request_id']
    def proposal(self,words):return {k:v for k,v in classify(normalize(words,'project')).items() if k in ('acts','constraints','targets','evidence_spans','unresolved')}
    def test_stages(self):
        for words,expected in [('상세 구현 계획 작성해','tasks'),('설계 작성해','design'),('구현해','implement'),('설계 변경하지 말고 구현해','implement'),('구현하면 위험하지 않아?','investigate'),('진행 상황 알려줘','investigate'),('계속해','resume')]:
            with self.subTest(words=words):self.assertEqual(classify(normalize(words,'project'))['acts'],[expected])
    def test_selector_and_quotes(self):
        line='''$skip --project project query record --input '{"kind":"plan","id":"abc","revision":2}'\n'''
        self.assertEqual(classify(normalize(line,'project'))['acts'],['answer'])
        self.assertEqual(classify(normalize(line+'구현해','project'))['acts'],['implement'])
        self.assertEqual(classify(normalize('> 구현해\n','project'))['acts'],['answer'])
        self.assertEqual(classify(normalize('“구현해”라는 문장을 검토해','project'))['acts'],['investigate'])
        with self.assertRaises(CoreError):normalize(line+line,'project')
        with self.assertRaises(CoreError):normalize(line,'other')
        with self.assertRaises(CoreError):normalize(line.rstrip()+'; rm file','project')
    def test_agent_cannot_ingest_or_bind(self):
        for op,p in [('input.ingest',{}),('response.bind',{'proposal_id':'x','revision':1})]:
            with self.assertRaises(CoreError):self.f.call(op,p)
    def test_tasks_requires_real_work_and_read_has_no_writes(self):
        words='상세 구현 계획 작성해';rid=self.request(words)
        self.f.call('intent.propose',{'request_id':rid,'expected_revision':1,'body':self.proposal(words)})
        count=self.f.db.connection.total_changes
        p=self.f.core.query('stage.assess',{'request_id':rid},self.f.actor(),self.f.ctx)['data']
        self.assertEqual(p['required_outputs'],['work_item']);self.assertIn('plan',p['missing_artifacts'])
        self.assertEqual(count,self.f.db.connection.total_changes)
    def test_quote_cannot_support_action_and_interpretation_is_cas(self):
        words='> 구현해\n설계 작성해';rid=self.request(words);body=self.proposal(words)
        self.f.call('intent.propose',{'request_id':rid,'expected_revision':1,'body':body})
        with self.assertRaises(CoreError):self.f.call('intent.propose',{'request_id':rid,'expected_revision':1,'body':body})
        body['evidence_spans']=[{'part_id':'0','start':0,'end':4}]
        with self.assertRaises(CoreError):self.f.call('intent.propose',{'request_id':rid,'expected_revision':2,'body':body})
    def test_legacy_unknown_and_immutable_history(self):
        r=self.f.request();data=self.f.core.query('entry.inspect',{'request_id':r['request_id']},self.f.actor())['data']
        self.assertEqual(data['provenance'],'verified')
        rid=self.request('설계 작성해')
        with self.assertRaises(Exception):self.f.db.connection.execute('DELETE FROM input_envelopes')
    def test_self_declared_provenance_rejected(self):
        with self.assertRaises(CoreError):self.f.call('input.ingest',{'verified':True},True)

    def test_native_response_requires_exact_revision_and_does_not_grant_execution(self):
        from dataclasses import replace
        rid=self.request('설계 작성해');self.f.work()
        proposal=self.f.call('action.propose',{'request_id':rid,'body':{'action':'implement','target':{'kind':'work_item','id':self.f.w['id'],'revision':1},'scope_digest':'0'*64,'constraints':[]}})
        actor=replace(self.f.actor(True,'그래 승인이야'),response_ref=(proposal['id'],1))
        result=self.f.core.execute(self.f.command('response.bind',{'proposal_id':proposal['id'],'revision':1}),actor,self.f.ctx)['data']
        self.assertEqual(result['authority'],'exact_response_only')
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM executions').fetchone()[0],0)
        self.f.ctx.can_continue=True
        with self.assertRaises(CoreError):self.f.core.execute(self.f.command('execution.begin_current',self.f.prepare),actor,self.f.ctx)

    def test_input_budget_and_cross_project(self):
        from skip_core.authority import Principal
        rid=self.request('설계 작성해')
        with self.assertRaises(CoreError):self.f.core.query('entry.inspect',{'request_id':rid},Principal('other','caller'))
        p=self.f.core.query('context',{'goal_id':self.f.goal,'stage':'design','request_id':rid,'budget':1024},self.f.actor(),self.f.ctx)['data']
        self.assertFalse(p['complete'])
