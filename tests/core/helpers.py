from pathlib import Path
import tempfile
from skip_core.db import Database
from skip_core.service import Core,DIMENSIONS
from skip_core.authority import ExecutionContext,Principal
from skip_core.common import uid

class Fixture:
    def __init__(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name)
        (self.root/'a.py').write_text('before')
        self.target=('host','workspace','provider','agent','thread','ui')
        self.ctx=ExecutionContext('project',{'main':self.root},self.target,lambda:self.target,can_start=True)
        self.db=Database(self.root/'private'/'skip.db',create=True);self.core=Core(self.db)
        self.call('project.activate',{'name':'Test'},human=True)

    def actor(self,human=False,words='Actual request',origin=None):
        return Principal('project',origin or self.ctx.context_id,kind='human' if human else 'agent',
                         method='native_user_action' if human else None,event_key=uid(),user_text=words)

    def command(self,op,p,key=None):
        return {'schema':'skip-core/v1','command':op,'key':key or uid(),'project_id':'project','payload':p}

    def call(self,op,p,human=False,words='Actual request'):
        return self.core.execute(self.command(op,p),self.actor(human,words),self.ctx)['data']

    def request(self):
        r=self.call('request.submit',{'text':'Actual request','operation':'implement'},True)
        self.request_id=r['request_id'];self.goal=r['goal']['id']; return r

    def publish(self,kind,fields,children=None,**kw):
        return self.call('record.propose_revision',dict(kind=kind,expected_revision=0,request_id=self.request_id,
                         goal_id=self.goal,fields=fields,children=children or {},**kw))

    def work(self,full=False,requirements=None,plans=None,path='a.py'):
        if not hasattr(self,'goal'):self.request()
        children={'checks':[{'check_id':'unit','description':'Unit check','surface':'unit','required':1}]}
        if requirements:children['requirements']=requirements
        if plans:children['plan_items']=plans
        w=self.publish('work_item',{'operation':'implement','title':'Change','instruction_body':'Change source','completion_definition':'Unit check',
                        'workflow_depth':'full' if full else 'compact','request_id':self.request_id},children)
        self.scope=[{'source_id':'main','relative_path':path,'access':'modify'}]
        factors={k:{'impact':'none','explanation':'Observed reversible local impact'} for k in DIMENSIONS}
        risk=self.call('risk.assess',{'goal_id':self.goal,'paths':self.scope,'goal_factors':factors,'change_factors':factors,'rationale':'Scoped change'})
        self.prepare={'work_id':w['id'],'revision':w['revision'],'goal_risk_id':risk['goal_risk_id'],'change_risk_id':risk['change_risk_id']}
        self.risk=risk;self.w=w
        return w

    def start(self):
        return self.call('execution.prepare',self.prepare,True)

    def close(self):
        self.db.close(); self.temp.cleanup()
