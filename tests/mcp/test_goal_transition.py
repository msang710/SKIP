import json,os,sys,unittest
from pathlib import Path
from datetime import timedelta
from unittest.mock import patch
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from tests.core.helpers import Fixture
from adapters.codex.entry import run

class NativeGoalToolTests(unittest.IsolatedAsyncioTestCase):
 async def test_real_mcp_calls_native_input_adapter(self):
  f=Fixture();self.addCleanup(f.close);f.work()
  home=f.root/'codex';sessions=home/'sessions';folder=sessions/'2026/09/12';folder.mkdir(parents=True)
  thread='01234567-1234-1234-1234-012345678901';path=folder/('rollout-'+thread+'.jsonl')
  events=[{'type':'session_meta','payload':{'id':thread,'cwd':str(f.root)}},{'type':'response_item','payload':{'type':'message','role':'user','id':'u1','content':[{'type':'input_text','text':'완료한 목표 정리해'}]}}]
  path.write_text(''.join(json.dumps(e)+'\n' for e in events))
  env={**os.environ,'CODEX_HOME':str(home),'CODEX_THREAD_ID':thread,'PYTHONPATH':str(Path.cwd())}
  with patch.dict(os.environ,env):entry=run(f.root,sessions,thread,f.db.path,project_id='project')['data']['entry_basis']
  goal=f.core.query('record',{'kind':'goal','id':f.goal},f.actor())['data']
  payload={'input_id':entry['input_id'],'input_digest':entry['input']['digest'],'evidence_spans':entry['suggestion']['evidence_spans'],'changes':[{'id':f.goal,'revision':goal['revision'],'state_version':goal['state_version'],'from_state':'active','to_state':'completed','reason':'완료 범위 확인','evidence':[]}]}
  params=StdioServerParameters(command=sys.executable,args=['-m','skip_mcp.server','--db',str(f.db.path),'--project','project','--workspace',str(f.root)],env=env)
  async with stdio_client(params) as (read,write):
   async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=10)) as client:
    await client.initialize()
    tools=await client.list_tools();self.assertIn('skip_update_goals',{t.name for t in tools.tools})
    r=await client.call_tool('skip_update_goals',payload);v=r.structuredContent or json.loads(r.content[0].text)
    self.assertEqual(v['status'],'ok',v);self.assertEqual(v['data']['goals'][0]['lifecycle'],'completed')
    r=await client.call_tool('skip_update_goals',payload);self.assertEqual(r.structuredContent or json.loads(r.content[0].text),v)
    events.append({'type':'response_item','payload':{'type':'message','role':'user','id':'u2','content':[{'type':'input_text','text':'상태만 보여줘'}]}})
    path.write_text(''.join(json.dumps(e)+'\n' for e in events))
    r=await client.call_tool('skip_update_goals',payload);v=r.structuredContent or json.loads(r.content[0].text)
    self.assertEqual(v['code'],'USER_ACTION_REQUIRED',v)
