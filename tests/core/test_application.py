import json
from pathlib import Path
import unittest
from unittest.mock import patch
from skip_core.common import uid
from skip_core.authority import Principal,ExecutionContext
from skip_core.db import Database
from skip_core.delivery import Delivery
from skip_core.errors import CoreError
from skip_core.service import Core
from tests.core.helpers import Fixture

class ApplicationTests(unittest.TestCase):
    def setUp(self):self.f=Fixture();self.addCleanup(self.f.close)
    def assertCode(self,code,fn):
        with self.assertRaises(CoreError) as error:fn()
        self.assertEqual(error.exception.code,code)

    def test_activation_creates_no_business_records(self):
        for table in ('requests','goals','decisions','plans','work_items','current_facts'):
            self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM '+table).fetchone()[0],0)

    def test_model_cannot_make_user_request_or_approve(self):
        self.assertCode('USER_ACTION_REQUIRED',lambda:self.f.call('request.submit',{'text':'Actual request','operation':'implement'}))
        self.f.work()
        self.assertCode('USER_ACTION_REQUIRED',lambda:self.f.call('execution.prepare',self.f.prepare))
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM authorizations').fetchone()[0],0)

    def test_idempotency_replay_and_changed_payload(self):
        p={'text':'Actual request','operation':'implement'}; actor=self.f.actor(True)
        cmd=self.f.command('request.submit',p)
        first=self.f.core.execute(cmd,actor,self.f.ctx)
        self.assertEqual(first,self.f.core.execute(cmd,actor,self.f.ctx))
        cmd['payload']['operation']='deploy'
        self.assertCode('CONFLICT',lambda:self.f.core.execute(cmd,actor,self.f.ctx))
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM goals').fetchone()[0],1)

    def test_compact_flow_no_artificial_plan_and_not_run_preserved(self):
        self.f.work();x=self.f.start(); sent=[]
        Delivery(self.f.core,self.f.ctx).send(x['execution_id'],lambda payload,key:sent.append(key) or {'message_key':key})
        self.assertEqual(len(sent),1)
        state=self.f.core.query('status',{'goal_id':self.f.goal},self.f.actor(),self.f.ctx)['data']
        self.assertEqual(state['remaining'][0]['state'],'NOT_RUN')
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM plans').fetchone()[0],0)

    def test_changed_source_blocks_before_prepare_and_send(self):
        self.f.work();(self.f.root/'a.py').write_text('changed')
        self.assertCode('STALE',self.f.start)
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM executions').fetchone()[0],0)
        (self.f.root/'a.py').write_text('before');x=self.f.start()
        (self.f.root/'a.py').write_text('after preparation')
        self.assertCode('STALE',lambda:Delivery(self.f.core,self.f.ctx).claim(x['execution_id']))

    def test_no_dispatch_to_another_context(self):
        self.f.work();x=self.f.start()
        other=ExecutionContext('project',self.f.ctx.sources,('other',),lambda:('other',),can_start=True)
        self.assertCode('CONTEXT_EXPIRED',lambda:Delivery(self.f.core,other).claim(x['execution_id']))
        self.f.target=('changed',)
        self.assertCode('STALE',lambda:Delivery(self.f.core,self.f.ctx).claim(x['execution_id']))

    def test_duplicate_and_overlapping_work_blocked(self):
        self.f.work();self.f.start()
        self.assertCode('EXECUTION_ACTIVE',self.f.start)
        self.f.work()
        self.assertCode('EXECUTION_ACTIVE',self.f.start)

    def test_pending_cancel_prevents_send(self):
        self.f.work();x=self.f.start()
        value=self.f.call('execution.cancel',{'execution_id':x['execution_id'],'expected_state_version':1},True)
        self.assertEqual(value['state'],'cancelled')
        self.assertCode('CONFLICT',lambda:Delivery(self.f.core,self.f.ctx).claim(x['execution_id']))

    def test_send_crash_is_unknown_and_never_retries(self):
        self.f.work();x=self.f.start();delivery=Delivery(self.f.core,self.f.ctx)
        def lost(*args):raise OSError('lost response')
        with self.assertRaises(OSError):delivery.send(x['execution_id'],lost)
        state=self.f.core.query('execution.status',{'execution_id':x['execution_id']},self.f.actor(),self.f.ctx)['data']
        self.assertEqual(state['delivery']['state'],'delivery_unknown')
        self.assertCode('CONFLICT',lambda:delivery.claim(x['execution_id']))
        self.assertCode('EXECUTION_ACTIVE',self.f.start)

    def test_cancel_during_dispatch_does_not_claim_completed_cancellation(self):
        self.f.work();x=self.f.start();delivery=Delivery(self.f.core,self.f.ctx);claim=delivery.claim(x['execution_id'])
        self.f.call('execution.cancel',{'execution_id':x['execution_id'],'expected_state_version':1},True)
        delivery.acknowledgement(claim,'accepted',receipt={'message_key':claim['message_key']})
        state=self.f.core.query('execution.status',{'execution_id':x['execution_id']},self.f.actor())['data']
        self.assertEqual(state['state'],'cancel_requested')

    def test_completed_work_can_continue_in_another_environment(self):
        self.f.work();x=self.f.start();d=Delivery(self.f.core,self.f.ctx);claim=d.claim(x['execution_id'])
        receipt={'message_key':claim['message_key']};d.acknowledgement(claim,'accepted',receipt=receipt);d.finish(x['execution_id'],receipt)
        self.f.ctx=ExecutionContext('project',self.f.ctx.sources,('B',),lambda:('B',),can_start=True)
        second=self.f.start()
        self.assertNotEqual(x['execution_id'],second['execution_id'])
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM work_items').fetchone()[0],1)
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM goals').fetchone()[0],1)

    def test_backup_reopen_and_future_schema_rejection(self):
        self.f.work();backup=self.f.root/'backup.db';self.f.db.backup(backup)
        with Database(backup) as db:
            self.assertEqual(db.connection.execute('SELECT count(*) FROM work_items').fetchone()[0],1)
            db.connection.execute("INSERT INTO schema_migrations VALUES(999,?,'now')", ("f"*64,))
        self.assertCode('UNSUPPORTED_SCHEMA',lambda:Database(backup))

    def test_goals_recent_changes_first_and_reads_preserve_order(self):
        self.f.request(); first=self.f.goal; first_request=self.f.request_id
        self.f.request(); second=self.f.goal
        def page(payload=None):
            return self.f.core.query('status',payload or {},self.f.actor(),self.f.ctx)['data']
        self.assertEqual([r['id'] for r in page()['goals']],[second,first])
        page({'goal_id':first})
        self.assertEqual([r['id'] for r in page()['goals']],[second,first])
        record=self.f.core.query('record',{'kind':'goal','id':first},self.f.actor(),self.f.ctx)['data']
        self.f.call('record.propose_revision',dict(kind='goal',id=first,expected_revision=record['revision'],
            request_id=first_request,goal_id=first,fields={**record['fields'],'title':'Updated goal'},children={}))
        one=page({'limit':1})
        self.assertEqual(one['goals'][0]['id'],first)
        self.assertEqual(page({'limit':1,'cursor':one['next_cursor']})['goals'][0]['id'],second)

    def test_settings_change_invalidates_risk(self):
        self.f.work()
        self.f.call('settings.update',{'scope':'project','expected_revision':0,'body':{'disabled_default_rule_ids':[],
             'custom_rules':[{'id':'r1','rule':'Check inventory','status':'active','scope':{'kind':'project'}}]}},True)
        self.assertCode('STALE',self.f.start)
        self.assertCode('STALE',lambda:self.f.call('settings.update',{'scope':'project','expected_revision':0,
                          'body':{'disabled_default_rule_ids':[],'custom_rules':[]}},True))

    def test_project_isolation_and_query_has_no_file_reader(self):
        self.f.work()
        self.assertCode('NOT_INITIALIZED',lambda:self.f.core.query('status',{},Principal('another','model')))
        with patch.object(Path,'read_text',side_effect=AssertionError('file reader called')):
            result=self.f.core.query('context',{'goal_id':self.f.goal,'stage':'implementation'},self.f.actor())
        self.assertTrue(result['data']['complete'])

    def test_evidence_and_now_preserve_provenance_and_freshness(self):
        self.f.work();x=self.f.start()
        observation=self.f.call('observation.record',{'paths':[dict(self.f.scope[0],access='read')],'summary':'Observed current source'})
        result=self.f.call('evidence.record',{'execution_id':x['execution_id'],'snapshot_id':observation['snapshot_id'],
            'surface':'unit','result':'PASS','summary':'Unit tests passed','method':'test command',
            'checks':[{'check_id':'unit','verdict':'PASS','explanation':'Test output'}]})
        self.assertEqual(result['provenance'],'agent_report')
        self.f.call('fact.record',{'evidence_id':result['evidence_id'],'source_id':'main','statement':'Source has the change'})
        status=self.f.core.query('status',{},self.f.actor(),self.f.ctx)['data']
        self.assertEqual(status['facts'][0]['freshness'],'current')
        (self.f.root/'a.py').write_text('edited later')
        status=self.f.core.query('status',{},self.f.actor(),self.f.ctx)['data']
        self.assertEqual(status['facts'][0]['freshness'],'stale')
        self.assertEqual(status['checks'][0]['result'],'PASS')

    def test_partial_aggregate_rolls_back_with_event(self):
        self.f.request();before=self.f.db.connection.execute('SELECT count(*) FROM events').fetchone()[0]
        self.assertCode('CONFLICT',lambda:self.f.publish('decision',{'question':'Choose','rationale':'Needed','risk_summary':'Risk'},
                            {'options':[{'option_id':'a','label':'A','description':'A','consequences':'A','recommended':1,'position':0}]}))
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM decisions').fetchone()[0],0)
        self.assertEqual(self.f.db.connection.execute('SELECT count(*) FROM events').fetchone()[0],before)

if __name__=='__main__':unittest.main()
