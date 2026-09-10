"""Application commands. All adapters use this transaction and authority boundary."""
import json
from .common import digest, encoded, identifier, now, text, uid
from .errors import CoreError, require
from .authority import snapshot
from . import records

DIMENSIONS = {'business_rules','inventory','money','permissions','sensitive_data','persisted_data','external_state','boot_recovery'}
ACTIVE = ('prepared','accepted','running','cancel_requested','cancellation_unknown')
OPERATIONS = {
 'project.activate': ({'name'}, set(), True),
 'request.submit': ({'text','operation'}, {'goal_id'}, True),
 'record.propose_revision': ({'kind','expected_revision','request_id','fields'}, {'id','goal_id','children'}, False),
 'record.lifecycle': ({'kind','id','expected_revision','lifecycle'}, set(), True),
 'decision.select': ({'decision_id','revision','option_id'}, set(), True),
 'risk.assess': ({'goal_id','paths','goal_factors','change_factors','rationale'}, set(), False),
 'execution.prepare': ({'work_id','revision','goal_risk_id','change_risk_id'}, {'selection'}, True),
 'execution.begin_current': ({'work_id','revision','goal_risk_id','change_risk_id'}, set(), True),
 'execution.finish_current': ({'execution_id'}, set(), True),
 'execution.cancel': ({'execution_id','expected_state_version'}, set(), True),
 'evidence.record': ({'snapshot_id','surface','result','summary','method'}, {'execution_id','checks','criteria','payload'}, False),
 'fact.record': ({'evidence_id','source_id','statement'}, {'goal_id','supersedes_id'}, False),
 'fact.retract': ({'fact_id','reason'}, set(), False),
 'settings.update': ({'scope','expected_revision','body'}, set(), True),
 'observation.record': ({'paths','summary'}, {'goal_id'}, False),
}


class Core:
    def __init__(self, db):
        self.db = db
        self.c = db.connection

    def query(self, query, payload, principal, context=None):
        from .queries import query_core
        with self.db.transaction(write=False):
            return query_core(self, query, payload, principal, context)

    def execute(self, command, principal, context=None):
        require(isinstance(command, dict) and set(command) == {'schema','command','key','project_id','payload'},
                'INVALID_INPUT', 'Invalid command envelope')
        require(command['schema'] == 'skip-core/v1', 'UNSUPPORTED_SCHEMA', 'Incompatible Core contract')
        project = identifier(command['project_id'])
        require(project == principal.project_id, 'PROJECT_MISMATCH', 'Project is outside this connection')
        op, payload = command['command'], command['payload']
        require(op in OPERATIONS and isinstance(payload, dict), 'INVALID_INPUT', 'Unknown command')
        required, optional, human = OPERATIONS[op]
        require(required <= set(payload) <= required | optional, 'INVALID_INPUT', 'Invalid command fields')
        require(len(encoded(command).encode()) <= 512_000, 'INVALID_INPUT', 'Command exceeds size limit')
        key = identifier(command['key'])
        if human:
            principal.human()
        if context is not None:
            require(context.project_id == project, 'PROJECT_MISMATCH', 'Context project mismatch')
            context.check()
        self.project, self.principal, self.context = project, principal, context
        self.command, self.key, self.counter = command, digest([principal.fingerprint,key]), 0
        with self.db.transaction():
            receipt = self.c.execute('SELECT * FROM command_receipts WHERE project_id=? AND principal_digest=? AND command_key=?',
                                     (project,principal.fingerprint,key)).fetchone()
            if receipt:
                require(receipt['command_digest'] == digest(command), 'CONFLICT', 'Idempotency key has different content')
                return json.loads(receipt['response_json'])
            exists = self.c.execute('SELECT state FROM projects WHERE id=?', (project,)).fetchone()
            if op == 'project.activate' and not exists:
                require(context is not None, 'CONTEXT_EXPIRED', 'Current source connection is required')
                records.insert(self.c,'projects',dict(id=project,name=text(payload['name'],256),state='active',created_at=now()))
                for source in context.sources:
                    records.insert(self.c,'sources',dict(project_id=project,id=identifier(source),name=source,kind='directory',logical_path='.',created_at=now()))
            else:
                require(exists and exists['state']=='active', 'NOT_INITIALIZED', 'Connect this project first')
            self.interaction = self._interaction(principal, command)
            self.event = self.event_record(op)
            handler = getattr(self, '_' + op.replace('.','_'))
            data = handler(payload)
            if context is not None:
                context.check()
            result = {'schema':'skip-core/v1','status':'ok','data':data,'enforcement':'advisory'}
            records.insert(self.c,'command_receipts',dict(project_id=project,principal_digest=principal.fingerprint,
                command_key=key,command_digest=digest(command),response_json=encoded(result),event_id=self.event))
            return result

    def _interaction(self, principal, command):
        external = principal.event_key or self.key
        body = principal.user_text if principal.kind == 'human' else encoded(command)
        origin = digest(principal.origin)
        old = self.c.execute('SELECT * FROM interactions WHERE project_id=? AND origin_context_digest=? AND external_event_key=?',
                             (self.project,origin,external)).fetchone()
        if old:
            require(old['body_digest']==digest(body) and old['actor_kind']==principal.kind, 'CONFLICT', 'Input event changed')
            return old['id']
        ident = uid()
        records.insert(self.c,'interactions',dict(project_id=self.project,id=ident,origin_context_digest=origin,
            external_event_key=external,actor_kind=principal.kind,body=body,body_digest=digest(body),created_at=now()))
        if principal.kind == 'human':
            principal.human()
            records.insert(self.c,'verified_interactions',dict(project_id=self.project,interaction_id=ident,method=principal.method,
                verifier=principal.verifier,proof_digest=digest([principal.fingerprint,external,body]),verified_at=now()))
        return ident

    def event_record(self, kind):
        self.counter += 1
        ident = uid()
        sequence = self.c.execute('SELECT COALESCE(max(sequence),0)+1 FROM events WHERE project_id=?',(self.project,)).fetchone()[0]
        records.insert(self.c,'events',dict(project_id=self.project,id=ident,sequence=sequence,interaction_id=self.interaction,
            command_key=self.key + '.' + str(self.counter),command_digest=digest(self.command),kind=kind,
            payload_json=encoded({'command':self.command['command']}),created_at=now()))
        return ident

    def one(self, table, ident):
        row = self.c.execute(f'SELECT * FROM {table} WHERE project_id=? AND id=?',(self.project,ident)).fetchone()
        require(row is not None,'NOT_FOUND','Record unavailable')
        return dict(row)

    def _project_activate(self, p):
        require(set(self.context.sources) == {r[0] for r in self.c.execute('SELECT id FROM sources WHERE project_id=?',(self.project,))},
                'PROJECT_MISMATCH','Connected sources differ from project')
        return {'project_id':self.project,'next_action':'request','goal_created':False}

    def new_request(self, intent, operation):
        require(operation in ('investigate','plan','implement','deploy'),'INVALID_INPUT','Invalid requested operation')
        self.principal.human()
        old=self.c.execute('SELECT * FROM requests WHERE project_id=? AND interaction_id=?',(self.project,self.interaction)).fetchone()
        if old:
            require(old['intent']==intent and (old['operation']==operation or operation=='investigate'), 'CONFLICT','User event already has a different request')
            return old['id']
        ident = uid()
        records.insert(self.c,'requests',dict(project_id=self.project,id=ident,interaction_id=self.interaction,
            operation=operation,intent=text(intent),intent_digest=digest(intent),created_at=now()))
        return ident

    def publish(self, p):
        ident, rev = records.publish(self.c,self.project,p,self.event,allow_new_goal=self.command['command']=='request.submit')
        records.advance(self.c,self.project,p['kind'],ident,rev,self.event_record('record.published'))
        return records.get(self.c,self.project,p['kind'],ident,rev)

    def _request_submit(self, p):
        require(p['text'] == self.principal.user_text,'USER_ACTION_REQUIRED','Request must match the actual user input')
        request = self.new_request(p['text'],p['operation'])
        if p.get('goal_id'):
            goal = records.get(self.c,self.project,'goal',p['goal_id'])
            require(goal['lifecycle']=='active','CONFLICT','Goal is not active')
        else:
            goal = self.publish({'kind':'goal','request_id':request,'expected_revision':0,
                'fields':{'title':p['text'][:160],'intent':p['text'],'success_definition':p['text']}})
        records.insert(self.c,'request_goals',dict(project_id=self.project,request_id=request,goal_id=goal['id']))
        return {'request_id':request,'goal':goal,'next_action':'investigate'}

    def _record_propose_revision(self, p):
        goal = p.get('goal_id') if p['kind'] != 'goal' else p.get('id')
        require(self.c.execute('SELECT 1 FROM request_goals WHERE project_id=? AND request_id=? AND goal_id=?',
                              (self.project,p['request_id'],goal)).fetchone(),'USER_ACTION_REQUIRED','Request is not linked to this goal')
        if p['kind']=='work_item':
            require(p['fields'].get('request_id')==p['request_id'],'INVALID_INPUT','Work request mismatch')
        return self.publish(p)

    def _record_lifecycle(self, p):
        record = records.get(self.c,self.project,p['kind'],p['id'])
        require(record['revision']==p['expected_revision'],'STALE','Record changed')
        require(p['lifecycle'] in ('active','held','archived'),'INVALID_INPUT','Invalid lifecycle')
        self.c.execute(f'UPDATE {p["kind"]}s SET lifecycle=?,state_version=state_version+1,last_event_id=? WHERE project_id=? AND id=?',
                       (p['lifecycle'],self.event,self.project,p['id']))
        return {'id':p['id'],'lifecycle':p['lifecycle']}

    def _decision_select(self, p):
        decision = records.get(self.c,self.project,'decision',p['decision_id'])
        require(decision['revision']==p['revision'],'STALE','Decision changed; review the new card')
        require(decision['lifecycle']=='active','STALE','Decision is no longer active')
        require(any(o['option_id']==p['option_id'] for o in decision['children']['options']),'INVALID_INPUT','Option unavailable')
        prior = self.c.execute('SELECT s.* FROM selections s WHERE project_id=? AND decision_id=? AND NOT EXISTS '
            '(SELECT 1 FROM selections n WHERE n.project_id=s.project_id AND n.supersedes_id=s.id)',(self.project,p['decision_id'])).fetchone()
        if prior and prior['decision_revision']==p['revision'] and prior['option_id']==p['option_id'] and not self.c.execute('SELECT 1 FROM selection_revocations WHERE project_id=? AND selection_id=?',(self.project,prior['id'])).fetchone():
            return {'selection_id':prior['id'],'decision_id':p['decision_id'],'revision':p['revision'],'option_id':p['option_id'],'execution_started':False}
        ident = uid()
        records.insert(self.c,'selections',dict(project_id=self.project,id=ident,decision_id=p['decision_id'],decision_revision=p['revision'],
            option_id=p['option_id'],interaction_id=self.interaction,event_id=self.event,supersedes_id=prior['id'] if prior else None,created_at=now()))
        return {'selection_id':ident,'decision_id':p['decision_id'],'revision':p['revision'],'option_id':p['option_id'],'execution_started':False}

    def current_settings(self):
        return [dict(r) for r in self.c.execute('SELECT s.id,v.revision,v.content_digest,v.validated_body_json FROM settings_sets s '
            'JOIN settings_versions v ON v.set_id=s.id AND v.revision=s.current_revision WHERE s.project_id=? OR s.scope_kind=? '
            'ORDER BY s.id',(self.project,'installation'))]

    def policy_digest(self):
        return digest({'version':'failure-cost/2','settings':self.current_settings()})

    def source_scope(self, paths, goal=None):
        require(self.context is not None,'CONTEXT_EXPIRED','A current source connection is required')
        snap = snapshot(self.context,paths)
        scope, snap_id = uid(), uid()
        records.insert(self.c,'scopes',dict(project_id=self.project,id=scope,goal_id=goal,summary='Explicit source scope',digest=digest(paths),created_at=now()))
        for path in paths:
            records.insert(self.c,'scope_paths',dict(project_id=self.project,scope_id=scope,**path))
        self.c.execute('UPDATE scopes SET sealed_at=? WHERE project_id=? AND id=?',(now(),self.project,scope))
        records.insert(self.c,'snapshots',dict(project_id=self.project,id=snap_id,scope_id=scope,digest=snap['digest'],created_at=now()))
        for entry in snap['entries']:
            records.insert(self.c,'snapshot_entries',dict(project_id=self.project,snapshot_id=snap_id,**entry))
        self.c.execute('UPDATE snapshots SET sealed_at=? WHERE project_id=? AND id=?',(now(),self.project,snap_id))
        return scope,snap_id

    def _risk_assess(self, p):
        goal = records.get(self.c,self.project,'goal',p['goal_id'])
        scope,snap = self.source_scope(p['paths'],goal['id'])
        result = {'scope_id':scope,'snapshot_id':snap,'next_action':'implement'}
        for kind in ('goal','change'):
            factors = p[kind+'_factors']
            require(isinstance(factors,dict) and set(factors)==DIMENSIONS,'INVALID_INPUT','All eight risk dimensions are required')
            for value in factors.values():
                require(isinstance(value,dict) and set(value)=={'impact','explanation'} and value['impact'] in ('none','material','unknown'),
                        'INVALID_INPUT','Invalid risk factor')
                text(value['explanation'],4096)
            impacts = [v['impact'] for v in factors.values()]
            level = 'unknown' if 'unknown' in impacts else 'high' if 'material' in impacts else 'low'
            if level=='unknown': result['next_action']='investigate'
            elif level=='high' and result['next_action']!='investigate': result['next_action']='design'
            ident=uid()
            records.insert(self.c,'risk_assessments',dict(project_id=self.project,id=ident,goal_id=goal['id'],goal_revision=goal['revision'],
                scope_id=scope,snapshot_id=snap,kind=kind,policy_version=self.policy_digest(),level=level,rationale=text(p['rationale']),
                assessor_interaction_id=self.interaction,digest=digest(factors),created_at=now()))
            for dimension,value in factors.items():
                records.insert(self.c,'risk_factors',dict(project_id=self.project,assessment_id=ident,dimension=dimension,**value))
            self.c.execute('UPDATE risk_assessments SET sealed_at=? WHERE project_id=? AND id=?',(now(),self.project,ident))
            result[kind+'_risk_id']=ident
        return result

    def _execution_prepare(self, p):
        from .execution import prepare
        return prepare(self,p)

    def _execution_begin_current(self, p):
        from .execution import prepare
        return prepare(self,p,current=True)

    def _execution_finish_current(self,p):
        from .execution import transition
        require(self.context is not None and self.context.can_continue,'CONTEXT_EXPIRED','Current native turn required')
        x=self.one('executions',p['execution_id'])
        require(x['dispatch_context_digest']==self.context.fingerprint and x['state']=='running','CONTEXT_EXPIRED','Execution does not belong to the current user turn')
        transition(self,'executions',x,'finished',finished_at=now(),result_receipt_digest=digest({'provenance':'agent_report','input':self.interaction}))
        return {'execution_id':x['id'],'state':'finished','provenance':'agent_report','validation_complete':False}

    def _execution_cancel(self, p):
        from .execution import cancel
        return cancel(self,p)

    def _evidence_record(self, p):
        from .evidence import record
        return record(self,p)

    def _fact_record(self, p):
        ev=self.one('evidence',p['evidence_id'])
        require(ev['result'] not in ('NOT_RUN','INCONCLUSIVE'),'INVALID_INPUT','Observed evidence required')
        if p.get('goal_id'):
            scope=self.one('scopes',self.one('snapshots',ev['snapshot_id'])['scope_id'])
            require(scope['goal_id']==p['goal_id'],'PROJECT_MISMATCH','Evidence belongs to another goal')
        require(self.c.execute('SELECT 1 FROM snapshot_entries WHERE project_id=? AND snapshot_id=? AND source_id=?',
                              (self.project,ev['snapshot_id'],p['source_id'])).fetchone(),'INVALID_INPUT','Fact source not observed')
        ident=uid()
        records.insert(self.c,'current_facts',dict(project_id=self.project,id=ident,goal_id=p.get('goal_id'),statement=text(p['statement']),
            source_id=p['source_id'],snapshot_id=ev['snapshot_id'],evidence_id=ev['id'],supersedes_id=p.get('supersedes_id'),event_id=self.event,created_at=now()))
        return {'fact_id':ident,'provenance':ev['provenance']}

    def _fact_retract(self,p):
        records.insert(self.c,'fact_retractions',dict(project_id=self.project,fact_id=p['fact_id'],event_id=self.event,reason=text(p['reason']),created_at=now()))
        return {'fact_id':p['fact_id'],'retracted':True}

    def _observation_record(self,p):
        require(all(x.get('access')=='read' for x in p['paths']),'INVALID_INPUT','Observations require read-only paths')
        if p.get('goal_id'):records.get(self.c,self.project,'goal',p['goal_id'])
        _,snap=self.source_scope(p['paths'],p.get('goal_id'))
        return self._evidence_record({'snapshot_id':snap,'surface':'source','result':'PASS','summary':p['summary'],'method':'current source snapshot'})

    def _settings_update(self,p):
        scope=p['scope']
        require(scope in ('project','installation'),'INVALID_INPUT','Invalid settings scope')
        require(scope!='installation' or self.principal.installation_admin,'USER_ACTION_REQUIRED','Installation settings require a local administrator action')
        body=p['body']
        require(isinstance(body,dict) and set(body)=={'disabled_default_rule_ids','custom_rules'},'INVALID_INPUT','Invalid settings body')
        require(isinstance(body['disabled_default_rule_ids'],list) and len(body['disabled_default_rule_ids'])<=10 and
                all(v in {f'C-{i:03}' for i in range(1,11)} for v in body['disabled_default_rule_ids']), 'INVALID_INPUT','Unknown default rule')
        require(isinstance(body['custom_rules'],list) and len(body['custom_rules'])<=128,'INVALID_INPUT','Too many rules')
        seen=set()
        for rule in body['custom_rules']:
            require(isinstance(rule,dict) and set(rule)=={'id','rule','status','scope'},'INVALID_INPUT','Invalid rule')
            identifier(rule['id']); text(rule['rule'],8192)
            require(rule['id'] not in seen and rule['status'] in ('active','disabled'),'INVALID_INPUT','Duplicate/invalid rule')
            seen.add(rule['id'])
            selector=rule['scope']
            require(selector=={'kind':'project'} or (isinstance(selector,dict) and set(selector)=={'kind','environment_id','operation'}
                    and selector['kind']=='environment-operation' and isinstance(selector['environment_id'],str)
                    and selector['operation'] in ('investigate','plan','implement','deploy')),'INVALID_INPUT','Invalid policy selector')
        ident='installation' if scope=='installation' else 'project.'+self.project
        old=self.c.execute('SELECT * FROM settings_sets WHERE id=?',(ident,)).fetchone()
        rev=old['current_revision'] if old else 0
        require(type(p['expected_revision']) is int and p['expected_revision']==rev,'STALE','Settings changed')
        if not old:
            records.insert(self.c,'settings_sets',dict(id=ident,scope_kind=scope,project_id=self.project if scope=='project' else None))
        records.insert(self.c,'settings_versions',dict(set_id=ident,revision=rev+1,validated_body_json=encoded(body),content_digest=digest(body),
            provenance_digest=digest([self.principal.fingerprint,self.interaction]),created_at=now()))
        self.c.execute('UPDATE settings_sets SET current_revision=?,state_version=state_version+1 WHERE id=?',(rev+1,ident))
        return {'settings_id':ident,'revision':rev+1,'policy_digest':self.policy_digest()}
