import json
import os
from pathlib import Path
import sys
import unittest
from datetime import timedelta
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from tests.core.helpers import Fixture

class ProtocolTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):self.f=Fixture();self.addCleanup(self.f.close);self.f.work()
    async def test_real_stdio_client_and_scope(self):
        params=StdioServerParameters(command=sys.executable,args=['-m','skip_mcp.server','--db',str(self.f.db.path),'--project','project','--workspace',str(self.f.root)],
                                     env={**os.environ,'PYTHONPATH':str(Path.cwd())})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=10)) as client:
                await client.initialize()
                tools=await client.list_tools();names={t.name for t in tools.tools}
                self.assertIn('skip_status',names)
                self.assertIn('skip_enter',names)
                from skip_core.input_contract import classify,normalize
                words='이 내용으로 새 목표 생성해'
                native=self.f.actor(True,words)
                captured=self.f.core.execute(self.f.command('input.ingest',{}),native,self.f.ctx)['data']
                input_read=await client.call_tool('skip_entry',{'input_id':captured['input_id']})
                entry=input_read.structuredContent or json.loads(input_read.content[0].text)
                self.assertEqual(entry['data']['suggestion']['acts'],['unresolved'])
                body={k:v for k,v in classify(normalize(words,'project')).items() if k in ('acts','constraints','targets','evidence_spans','unresolved')}
                body.update(acts=['create_goal'],unresolved=[])
                entry_args={'input_id':captured['input_id'],'input_digest':captured['digest'],'expected_revision':0,'body':body,'target':{'mode':'create','fields':{'title':'MCP goal','intent':words,'success_definition':'Stored'}},'records':[],'submission_id':'mcp-entry'}
                entered=await client.call_tool('skip_enter',entry_args)
                entered_value=entered.structuredContent or json.loads(entered.content[0].text)
                self.assertEqual(entered_value['status'],'ok',entered_value)
                self.assertEqual(entered_value['data']['authority'],'records_only')
                again=await client.call_tool('skip_enter',entry_args)
                self.assertEqual(again.structuredContent or json.loads(again.content[0].text),entered_value)

                self.assertIn('skip_project_profile',names)
                self.assertIn('skip_propose_project_profile',names)
                profile=await client.call_tool('skip_project_profile',{})
                v=profile.structuredContent or json.loads(profile.content[0].text)
                self.assertFalse(v['data']['metadata']['available'])
                proposed=await client.call_tool('skip_propose_project_profile',{'expected_revision':None,'tagline':'Project','body_markdown':'Purpose','key':'profile-propose'})
                v=proposed.structuredContent or json.loads(proposed.content[0].text)
                self.assertEqual(v['data']['state'],'proposed')
                profile=await client.call_tool('skip_project_profile',{})
                v=profile.structuredContent or json.loads(profile.content[0].text)
                self.assertIsNone(v['data']['profile'])
                from tests.core.test_authoring import AuthoringTests
                self.assertTrue({'skip_submit','skip_amend','skip_result'}<=names)
                schema=next(t.inputSchema for t in tools.tools if t.name=='skip_submit')
                self.assertIn('planFields',schema['$defs'])
                base={'goal_id':self.f.goal,'request_id':self.f.request_id}
                args={'base':base,'records':[AuthoringTests().plan()],'submission_id':'bundle'}
                created=await client.call_tool('skip_submit',args)
                value=created.structuredContent or json.loads(created.content[0].text)
                self.assertEqual(value['status'],'ok',value)
                plan=value['data']['records'][0]
                repeated=await client.call_tool('skip_submit',args)
                self.assertEqual(repeated.structuredContent or json.loads(repeated.content[0].text),value)
                changed=await client.call_tool('skip_amend',{'base':base,'changes':[{'target':{k:plan[k] for k in ('kind','id','revision')},'set_fields':{'title':'Revised'}}],'submission_id':'amend'})
                value=changed.structuredContent or json.loads(changed.content[0].text)
                self.assertEqual(value['data']['records'][0]['revision'],2)
                observation=await client.call_tool('skip_observe',{'goal_id':self.f.goal,'paths':[{'source_id':'main','relative_path':'a.py','access':'read'}],'summary':'scope','key':'observe'})
                value=observation.structuredContent or json.loads(observation.content[0].text)
                evidence=await client.call_tool('skip_result',{'base':base,'snapshot_id':value['data']['snapshot_id'],'evidence':{'surface':'unit','result':'PASS','summary':'Checked','method':'test'},'submission_id':'result'})
                value=evidence.structuredContent or json.loads(evidence.content[0].text)
                self.assertEqual(value['data']['evidence']['provenance'],'agent_report')
                self.assertFalse(value['data']['execution_finished'])
                self.assertIn('skip_learning',names)
                listing=await client.call_tool('skip_learning',{'query_name':'learning.list','payload':{'kind':'failure'}})
                v=listing.structuredContent or json.loads(listing.content[0].text)
                self.assertEqual(v['data']['items'],[])
                blocked=await client.call_tool('skip_record_learning',{'operation':'learning.accept','payload':{},'key':'deny'})
                v=blocked.structuredContent or json.loads(blocked.content[0].text)
                self.assertEqual(v['code'],'USER_ACTION_REQUIRED')
                self.assertIn('skip_requests',names);self.assertIn('skip_request',names)
                saved=await client.call_tool('skip_request',{'id':self.f.request_id})
                value=saved.structuredContent or json.loads(saved.content[0].text)
                self.assertEqual(value['data']['intent'],'Actual request')
                self.assertNotIn('decision.select',names);self.assertNotIn('execution.prepare',names)
                status=await client.call_tool('skip_status',{'goal_id':self.f.goal})
                value=status.structuredContent or json.loads(status.content[0].text)
                self.assertEqual(value['data']['remaining'][0]['state'],'NOT_RUN')
                self.assertEqual(value['sequence'],self.f.core.query('status',{},self.f.actor())['sequence'])
                context=await client.call_tool('skip_context',{'goal_id':self.f.goal,'stage':'implementation','budget':1024})
                value=context.structuredContent or json.loads(context.content[0].text)
                self.assertFalse(value['data']['complete'])
                raw=await client.read_resource('skip://projects/project/now')
                self.assertEqual(json.loads(raw.contents[0].text)['project_id'],'project')
                with self.assertRaises(Exception):await client.read_resource('skip://projects/other/now')
                ui=await client.read_resource('ui://skip/decision-inbox')
                self.assertIn('lang="ko"',ui.contents[0].text)
                self.assertNotIn('execution.prepare',ui.contents[0].text)
                bad=await client.call_tool('skip_propose',{'kind':'goal','request_id':self.f.request_id,'goal_id':self.f.goal,
                    'fields':{'title':'Invented','intent':'Unrequested','success_definition':'Invented'},'children':{},'key':'fake-goal'})
                value=bad.structuredContent or json.loads(bad.content[0].text)
                self.assertEqual(value['status'],'error')

if __name__=='__main__':unittest.main()
