"""Local fixture-only comparison; no installed SKIP runtime or business DB."""
import json, subprocess, sys, time
from pathlib import Path
from tests.core.helpers import Fixture
from tests.core.test_authoring import AuthoringTests

def run(mode):
    f=Fixture()
    try:
        f.request()
        base={'goal_id':f.goal,'request_id':f.request_id}
        rows=[AuthoringTests().plan()]
        for i in range(14):
            rows.append({'client_ref':f'w{i}','kind':'work_item','fields':{
                'operation':'implement','title':f'Task {i}','instruction_body':'Implement the planned change.',
                'completion_definition':'Required test passes.','workflow_depth':'compact'},'children':{
                'plan_items':[{'plan_id':'$p','plan_item_id':'step','rationale':'design'}],
                'checks':[{'description':'Check behavior','surface':'unit','required':1}]}})
        calls=0;sent=0;received=0
        def cli(action,payload):
            nonlocal calls,sent,received
            raw=json.dumps(payload);sent+=len(raw.encode());calls+=1
            args=[sys.executable,'-m','skip_core.cli','--db',str(f.db.path),'--project','project',
                  '--workspace',str(f.root),'--receipt-scope','benchmark',action]
            if action=='submit':args+=['--submission-id','bundle']
            result=subprocess.run(args,input=raw,text=True,capture_output=True,check=True)
            received+=len(result.stdout.encode())
            return json.loads(result.stdout)['data']
        start=time.perf_counter()
        if mode=='bundle':
            saved=cli('submit',{'base':base,'records':rows})['records']
        else:
            saved=[]
            for i,row in enumerate(rows):
                fields=dict(row['fields']);children=row['children']
                if i:
                    fields['request_id']=f.request_id
                    children['plan_items'][0].update(plan_id=saved[0]['id'],plan_revision=1)
                    children['checks'][0]['check_id']='test'
                else:children['items'][0]['position']=0
                saved.append(cli('command',f.command('record.propose_revision',{'kind':row['kind'],
                    **base,'expected_revision':0,'fields':fields,'children':children})))
        assert len(saved)==15
        return {'processes':calls,'write_calls':calls,'input_bytes':sent,'output_bytes':received,
                'wall_seconds':round(time.perf_counter()-start,4),'records':len(saved)}
    finally:f.close()

if __name__=='__main__':
    print(json.dumps({'scope':'Temporary SQLite DBs, same plan and 14 tasks; excludes model writing time and deployment',
                      'legacy':run('legacy'),'bundle':run('bundle')},indent=2))
