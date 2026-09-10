import json
from pathlib import Path
import unittest
from jsonschema import Draft202012Validator
from tests.core.helpers import Fixture

class ContractTests(unittest.TestCase):
    def test_public_schema_and_core_response_agree(self):
        schema=json.loads((Path(__file__).resolve().parents[2]/'schemas/skip-core-v1.json').read_text())
        Draft202012Validator.check_schema(schema)
        f=Fixture();self.addCleanup(f.close)
        Draft202012Validator(schema).validate(f.command('request.submit',{'text':'Actual request','operation':'implement'}))
        response={**schema,'$ref':'#/$defs/response'}
        Draft202012Validator(response).validate(f.core.query('status',{},f.actor()))
        f.work()
        value=f.core.query('context',{'goal_id':f.goal,'stage':'implementation','budget':1024},f.actor(),f.ctx)
        self.assertFalse(value['data']['complete'])
        self.assertLessEqual(len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode()),1024)

    def test_current_turn_execution_does_not_send_or_claim_validation(self):
        f=Fixture();self.addCleanup(f.close);f.work();f.ctx.can_continue=True
        result=f.call('execution.begin_current',f.prepare,True)
        self.assertEqual(result['authorization'],'ALLOW')
        state=f.core.query('execution.status',{'execution_id':result['execution_id']},f.actor(),f.ctx)['data']
        self.assertEqual(state['state'],'running')
        done=f.call('execution.finish_current',{'execution_id':result['execution_id']},True)
        self.assertFalse(done['validation_complete'])
        status=f.core.query('status',{},f.actor(),f.ctx)['data']
        self.assertEqual(status['remaining'][0]['state'],'NOT_RUN')

    def test_recovery_receipt_resolves_unknown_without_restoring_route(self):
        from skip_core.delivery import Delivery
        from skip_core.authority import ExecutionContext
        from skip_core.errors import CoreError
        f=Fixture();self.addCleanup(f.close);f.work();x=f.start()
        delivery=Delivery(f.core,f.ctx);claim=delivery.claim(x['execution_id'])
        delivery.acknowledgement(claim,'unknown')
        f.ctx.close()
        fresh=ExecutionContext('project',{'main':f.root},('new-host','new-thread'),lambda:('new-host','new-thread'))
        recovery=Delivery(f.core,fresh)
        with self.assertRaises(CoreError):recovery.reconcile(x['execution_id'],{'message_key':'other','lookup_receipt':'host-result'},outcome='accepted')
        result=recovery.reconcile(x['execution_id'],{'message_key':claim['message_key'],'lookup_receipt':'exact-host-result'},outcome='accepted',state='finished')
        self.assertEqual(result['sent'],0);self.assertFalse(result['route_restored'])
        self.assertFalse(result['validation_complete'])
