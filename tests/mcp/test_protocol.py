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
