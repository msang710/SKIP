import json
import unittest
from tests.core.helpers import Fixture
from skip_core.errors import CoreError
from skip_core.authority import Principal

class LearningTests(unittest.TestCase):
    def setUp(self):
        self.f=Fixture();self.addCleanup(self.f.close);self.f.request();self.snap=self.f.call('observation.record',{'goal_id':self.f.goal,'paths':[{'source_id':'main','relative_path':'a.py','access':'read'}],'summary':'Observed source'})['snapshot_id']
    def ev(self,result='PASS',surface='unit',**kw):
        return self.f.call('evidence.record',{'snapshot_id':self.snap,'result':result,'surface':surface,'summary':'test '+result,'method':'controlled fixture',**kw})
    def prop(self,kind,body,links=None,**kw):
        return self.f.call('learning.propose',{'kind':kind,'expected_revision':0,'goal_id':self.f.goal,'body':body,'links':links or [],**({'snapshot_id':self.snap} if kind=='claim' else {}),**kw})
    def link(self,r,role):return {'role':role,'kind':r['kind'],'id':r['id'],'revision':r['revision']}
    def query(self,name,p):return self.f.core.query(name,p,self.f.actor(),self.f.ctx)['data']
    def setup_claim(self,phase='before_deploy',fault=False):
        claim=self.prop('claim',{'title':'No duplicate assignment','statement':'Actual DB concurrency','assumptions':'postgres','limitations':'finite tested schedules'})
        boundary=self.prop('boundary',{'title':'DB race','description':'Multiple real DB connections'})
        profile=self.prop('environment',{'title':'actual DB','requirements':{'db':{'op':'eq','value':'postgres'},'connections':{'op':'gte','value':2}}})
        obligation=self.prop('obligation',{'title':'Preserve invariant','expected':'No duplicate','acceptance':'zero duplicates','phase':phase,'required':True},[self.link(claim,'claim'),self.link(boundary,'boundary'),self.link(profile,'environment')])
        scenario=self.prop('scenario',{'title':'race','kind':'fault' if fault else 'concurrency','trigger':'two requests','invariant':'no duplicates','oracle':'query assignments','cleanup':'rollback fixture','fault':{'mode':'random','target':'api','kind':'500','probability':0.1,'seed':42,'schedule':'record actual events'} if fault else None},[self.link(obligation,'obligation')])
        return claim,obligation,scenario
    def run_case(self,scenario,result='PASS',env=None,injection='PASS',count=1):
        env=env or {'db':'postgres','connections':2}
        e=self.ev(surface='source',payload={'media_type':'application/json','text':json.dumps(env)})
        run=self.f.call('verification.run.start',{'scenario_id':scenario['id'],'revision':1,'snapshot_id':self.snap,'environment_evidence_id':e['evidence_id'],'environment':env})
        e=self.ev(result)
        self.f.call('verification.run.finish',{'run_id':run['id'],'evidence_id':e['evidence_id'],'injection':injection,'behavior':result,'recovery':'NOT_RUN','trace':{'attempts':10,'injected':count,'events':['api:500'] if count else []}})
        return run
    def test_fail_then_pass_is_preserved_and_retry_is_idempotent(self):
        e=self.ev('FAIL');self.ev('PASS')
        row=self.f.db.connection.execute('SELECT * FROM failure_occurrences').fetchone();self.assertIsNotNone(row)
        r=self.f.call('failure.report',{'evidence_id':e['evidence_id'],'classification':'product'})
        self.assertEqual(r['id'],row['id']);self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM failure_occurrences').fetchone()[0],1)
        with self.assertRaises(Exception):self.f.db.connection.execute("DELETE FROM failure_occurrences")
    def test_environment_boundary_and_conflicting_runs(self):
        c,o,s=self.setup_claim()
        self.run_case(s,env={'db':'mock','connections':2})
        p={'claim_id':c['id'],'snapshot_id':self.snap}
        self.assertEqual(self.query('assurance',p)['verdict'],'undetermined')
        self.run_case(s);self.assertEqual(self.query('assurance',p)['verdict'],'supported')
        self.run_case(s,'FAIL');self.assertEqual(self.query('assurance',p)['verdict'],'undetermined')
        self.assertEqual(self.query('assurance',p)['items'][0]['result'],'conflict')
    def test_random_without_injection_does_not_pass(self):
        c,o,s=self.setup_claim(fault=True)
        with self.assertRaises(CoreError):self.run_case(s,count=0)
        self.run_case(s,injection='NOT_RUN',count=0)
        self.assertEqual(self.query('assurance',{'claim_id':c['id'],'snapshot_id':self.snap})['verdict'],'undetermined')
    def test_empty_claim_is_not_supported(self):
        c=self.prop('claim',{'title':'untested','statement':'works','assumptions':'unknown','limitations':'unknown'})
        self.assertEqual(self.query('assurance',{'claim_id':c['id'],'snapshot_id':self.snap})['verdict'],'undetermined')
    def test_native_authority_required_to_accept(self):
        c,o,s=self.setup_claim()
        with self.assertRaises(CoreError) as e:self.f.call('learning.accept',{'kind':'claim','id':c['id'],'revision':1,'selection_id':'missing'})
        self.assertEqual(e.exception.code,'USER_ACTION_REQUIRED')
    def test_guidance_freshness_and_context_budget(self):
        g=self.prop('guideline',{'title':'Avoid same bug','conditions':'changing a.py','action':'test race','verification':'race test','state':'active','targets':[{'source_id':'main','path':'a.py'}]})
        e=self.ev()
        self.f.call('guideline.assess',{'guideline_id':g['id'],'revision':1,'goal_id':self.f.goal,'snapshot_id':self.snap,'evidence_id':e['evidence_id'],'applicability':'applies','outcome':'not_reproduced','rationale':'controlled test'})
        p={'goal_id':self.f.goal,'snapshot_id':self.snap}
        self.assertEqual(self.query('guidance',p)['items'][0]['assessment']['freshness'],'current')
        (self.f.root/'a.py').write_text('changed')
        self.assertEqual(self.query('guidance',p)['items'][0]['assessment']['freshness'],'stale')
        pack=self.query('context',{'goal_id':self.f.goal,'stage':'implementation','budget':1024})
        self.assertFalse(pack['complete'])
    def test_other_project_cannot_read_learning(self):
        c,o,s=self.setup_claim()
        with self.assertRaises(CoreError):self.f.core.query('learning.record',{'kind':'claim','id':c['id']},Principal('other','caller'))
    def test_no_typed_reference_escape(self):
        c,o,s=self.setup_claim()
        with self.assertRaises(CoreError):self.prop('scenario',s['body'],[{'role':'obligation','kind':'claim','id':c['id'],'revision':1}])

    def accept(self,row):
        d=self.f.publish('decision',{'question':'Accept '+row['kind'],'rationale':'Exact contract','risk_summary':'Bounded scope'}, {'options':[
            {'option_id':'yes','label':'Accept','description':'Accept this revision','consequences':'Apply','recommended':1,'position':0},
            {'option_id':'no','label':'Reject','description':'Do not apply','consequences':'Leave candidate','recommended':0,'position':1}]})
        selection=self.f.call('decision.select',{'decision_id':d['id'],'revision':1,'option_id':'yes'},True)
        self.f.call('learning.accept',{'kind':row['kind'],'id':row['id'],'revision':row['revision'],'selection_id':selection['selection_id']},True)
    def test_preflight_phases_do_not_deadlock_repair(self):
        c,o,s=self.setup_claim(phase='after_deploy')
        self.accept(c);self.f.work()
        # After-deploy obligations do not prevent implementation of their repair.
        self.assertEqual(self.f.start()['state'],'prepared')
    def test_required_preflight_blocks_missing_evidence(self):
        c,o,s=self.setup_claim(phase='before_implementation');self.accept(c);self.f.work()
        with self.assertRaises(CoreError) as e:self.f.start()
        self.assertEqual(e.exception.code,'ASSURANCE_INCOMPLETE')
    def test_confirmed_cause_requires_observed_evidence(self):
        self.ev('FAIL');case=self.query('learning.list',{'kind':'failure'})['items'][0]
        with self.assertRaises(CoreError):self.f.call('learning.propose',{'kind':'failure','id':case['id'],'expected_revision':1,'goal_id':self.f.goal,'body':{**case['body'],'cause_state':'confirmed'}})
    def test_accepted_boundary_cannot_silently_change(self):
        c,o,s=self.setup_claim();self.accept(c)
        self.f.call('learning.propose',{'kind':'scenario','id':s['id'],'expected_revision':1,'goal_id':self.f.goal,'body':{**s['body'],'oracle':'weaker check'},'links':s['links']})
        self.f.work()
        with self.assertRaises(CoreError) as e:self.f.start()
        self.assertEqual(e.exception.code,'STALE')

    def test_reobserving_same_source_does_not_erase_failure(self):
        c,o,s=self.setup_claim();self.run_case(s,'FAIL')
        self.snap=self.f.call('observation.record',{'goal_id':self.f.goal,'paths':[{'source_id':'main','relative_path':'a.py','access':'read'}],'summary':'same source again'})['snapshot_id']
        self.run_case(s,'PASS')
        result=self.query('assurance',{'claim_id':c['id'],'snapshot_id':self.snap})
        self.assertEqual(result['items'][0]['result'],'conflict')
    def test_failure_attempts_remain_readable(self):
        e=self.ev('FAIL');case=self.query('learning.list',{'kind':'failure'})['items'][0]
        self.f.call('failure.attempt.record',{'case_id':case['id'],'evidence_id':e['evidence_id'],'action':'Retry did not help'})
        self.ev('PASS')
        result=self.query('learning.record',{'kind':'failure','id':case['id']})
        self.assertEqual(len(result['occurrences']),1);self.assertEqual(result['attempts'][0]['action_body'],'Retry did not help')
    def test_wrong_scope_cannot_support_claim(self):
        c,o,s=self.setup_claim();(self.f.root/'other.py').write_text('other')
        other=self.f.call('observation.record',{'goal_id':self.f.goal,'paths':[{'source_id':'main','relative_path':'other.py','access':'read'}],'summary':'different scope'})
        with self.assertRaises(CoreError) as e:self.query('assurance',{'claim_id':c['id'],'snapshot_id':other['snapshot_id']})
        self.assertEqual(e.exception.code,'SCOPE_MISMATCH')

    def test_dependency_across_phases_and_failed_dependent(self):
        from skip_core.assurance import evaluate
        c,early,s=self.setup_claim(phase='before_implementation')
        later=self.prop('obligation',{**early['body'],'phase':'before_deploy'},early['links']+[self.link(early,'dependency')])
        later_s=self.prop('scenario',s['body'],[self.link(later,'obligation')])
        self.run_case(s);self.run_case(later_s)
        result=evaluate(self.f.core,c['id'],self.snap,'before_deploy')
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['verdict'],'supported')
        # A dependency becoming unresolved cannot hide the dependent's own failure.
        c2,early2,s2=self.setup_claim(phase='before_implementation')
        later2=self.prop('obligation',{**early2['body'],'phase':'before_deploy'},early2['links']+[self.link(early2,'dependency')])
        failing=self.prop('scenario',s2['body'],[self.link(later2,'obligation')])
        self.run_case(failing,'FAIL')
        self.assertEqual(evaluate(self.f.core,c2['id'],self.snap,'before_deploy')['verdict'],'contradicted')
