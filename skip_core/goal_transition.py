"""Native user-request goal transitions; a receipt never grants execution rights."""
from . import records
from .errors import require
from .common import text,identifier

OPS={'goal.transition':({'input_id','input_digest','evidence_spans','changes'},set(),True),
     'goal.set_state':({'id','revision','state_version','from_state','to_state'},set(),True)}
STATES={'active','held','completed','archived'}


def transition(core,p):
    from .entry_runtime import ingest
    captured=ingest(core,{})
    require(p['input_id']==captured['input_id'] and p['input_digest']==captured['digest'],
            'USER_ACTION_REQUIRED','Use the input_id and digest of this actual current user request')
    from .input_authoring import lookup
    from .entry_runtime import validate_body
    _,envelope=lookup(core,captured['input_id'])
    from .input_contract import classify
    validate_body(core,{'acts':['record'],'constraints':classify(envelope)['constraints'],'targets':envelope['targets'],
                       'evidence_spans':p['evidence_spans'],'unresolved':[]},envelope)
    selected_goals={records.get(core.c,core.project,r['kind'],r['id'],r['revision'])['goal_id'] for r in envelope['targets']}
    result=apply_changes(core,p['changes'],selected_goals)
    return dict(result,input_id=captured['input_id'],input_digest=captured['digest'])

def set_state(core,p):
    require(core.principal.method=='native_user_action','USER_ACTION_REQUIRED','Use a native UI action')
    return apply_changes(core,[dict(p,reason='사용자가 UI에서 직접 상태 변경',evidence=[])])

def apply_changes(core,changes,selected_goals=()):
    require(isinstance(changes,list) and 0<len(changes)<=64,'INVALID_INPUT','Submit 1 to 64 goal changes')
    seen=set();prepared=[]
    for change in changes:
        require(isinstance(change,dict) and set(change)=={'id','revision','state_version','from_state','to_state','reason','evidence'},'INVALID_INPUT','Exact goal transition fields required')
        identifier(change['id'])
        require(change['id'] not in seen,'INVALID_INPUT','Duplicate goal transition');seen.add(change['id'])
        require(type(change['revision']) is int and type(change['state_version']) is int,'INVALID_INPUT','Integer revision/state_version required')
        require(isinstance(change['from_state'],str) and isinstance(change['to_state'],str) and change['from_state'] in STATES and change['to_state'] in STATES and change['from_state']!=change['to_state'],'INVALID_INPUT','Choose a different goal state')
        reason=text(change['reason'])
        goal=records.get(core.c,core.project,'goal',change['id'],change['revision'])
        require(not selected_goals or goal['id'] in selected_goals,'PROJECT_MISMATCH','Change exceeds explicitly selected goal')
        head=core.one('goals',change['id'])
        require(goal['revision']==goal['current_revision'] and head['state_version']==change['state_version'] and head['lifecycle']==change['from_state'],
                'STALE','Goal content or lifecycle changed; refresh this goal before retrying')
        require(isinstance(change['evidence'],list) and len(change['evidence'])<=32,'INVALID_INPUT','Bounded evidence references required')
        for ref in change['evidence']:
            require(isinstance(ref,dict) and set(ref)=={'kind','id','revision'} and type(ref['revision']) is int and isinstance(ref['kind'],str),'INVALID_INPUT','Exact supporting record required')
            identifier(ref['id'])
            if ref['kind']=='evidence':
                require(ref['revision']==1,'INVALID_INPUT','Evidence is immutable revision 1')
                ev=core.one('evidence',ref['id']);scope=core.one('scopes',core.one('snapshots',ev['snapshot_id'])['scope_id'])
                require(scope['goal_id']==goal['id'],'PROJECT_MISMATCH','Evidence belongs to another goal')
            else:
                supporting=records.get(core.c,core.project,ref['kind'],ref['id'],ref['revision'])
                require(supporting['goal_id']==goal['id'],'PROJECT_MISMATCH','Supporting record belongs to another goal')
                require(supporting['revision']==supporting['current_revision'],'STALE','Supporting record changed')
        if change['to_state']!='active':
            active=core.c.execute("SELECT 1 FROM executions x JOIN work_items w ON w.project_id=x.project_id AND w.id=x.work_item_id WHERE x.project_id=? AND w.goal_id=? AND x.state IN ('prepared','accepted','running','cancel_requested','cancellation_unknown') LIMIT 1",(core.project,goal['id'])).fetchone()
            require(not active,'EXECUTION_ACTIVE','Resolve active execution before closing or holding its goal')
        prepared.append((change,goal,reason))
    result=[]
    for change,goal,reason in prepared:
        from .record_state import apply
        apply(core,'goal',goal['id'],goal['revision'],change['to_state'],reason=reason)
        result.append({'id':goal['id'],'title':goal['fields']['title'],'revision':goal['revision'],
                       'state_version':change['state_version']+1,'from_state':change['from_state'],'lifecycle':change['to_state'],
                       'reason':reason,'evidence':change['evidence']})
    return {'committed':True,'goals':result,
            'authority':'goal_lifecycle_only','validation_changed':False,'execution_authorized':False}

HANDLERS={'goal.transition':transition,'goal.set_state':set_state}
