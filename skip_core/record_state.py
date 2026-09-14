"""Shared lifecycle mutation, immutable history and exact replacement references."""
from . import records
from .common import identifier, now, text, uid
from .errors import require

DOCUMENTS = ('decision','requirement','plan','work_item')
STATES = {'goal':('active','held','completed','archived'), **{k:('active','held','rejected','superseded','archived') for k in DOCUMENTS}}
OPS = {'record.set_state': ({'kind','id','revision','state_version','from_state','to_state'}, {'reason','replacement'}, True)}

def metadata(c,project,kind,ident):
    row=c.execute('SELECT * FROM record_state_changes WHERE project_id=? AND kind=? AND record_id=? ORDER BY state_version DESC LIMIT 1',(project,kind,ident)).fetchone()
    return decode(row) if row else None

def decode(row):
    value=dict(row)
    value['replacement']=({'kind':row['kind'],'id':row['replacement_id'],'revision':row['replacement_revision']} if row['replacement_id'] else None)
    return value

def ensure_idle(core,goal):
    active=core.c.execute("SELECT 1 FROM executions x JOIN work_items w ON w.project_id=x.project_id AND w.id=x.work_item_id WHERE x.project_id=? AND w.goal_id=? AND x.state IN ('prepared','accepted','running','cancel_requested','cancellation_unknown') LIMIT 1",(core.project,goal)).fetchone()
    require(not active,'EXECUTION_ACTIVE','Resolve active goal execution before changing record state')

def apply(core,kind,ident,revision,to_state,*,reason='',replacement=None):
    r=records.get(core.c,core.project,kind,ident)
    require(r['revision']==revision,'STALE','Record content changed')
    require(isinstance(to_state,str) and to_state in STATES[kind],'INVALID_INPUT','Invalid record lifecycle')
    if kind!='goal' or to_state!='active':ensure_idle(core,r['goal_id'])
    require(isinstance(reason,str),'INVALID_INPUT','Reason must be text')
    if reason:reason=text(reason)
    if to_state in ('rejected','superseded'):require(bool(reason.strip()),'INVALID_INPUT','A reason is required')
    if to_state=='superseded':
        require(isinstance(replacement,dict) and set(replacement)=={'kind','id','revision'},'INVALID_INPUT','Exact replacement required')
        require(replacement['kind']==kind and replacement['id']!=ident and type(replacement['revision']) is int,'INVALID_INPUT','Choose another record of the same kind')
        identifier(replacement['id'])
        target=records.get(core.c,core.project,kind,replacement['id'],replacement['revision'])
        require(target['goal_id']==r['goal_id'],'PROJECT_MISMATCH','Replacement must belong to the same goal')
        require(target['lifecycle']=='active' and target['revision']==target['current_revision'],'STALE','Replacement is no longer current and active')
    else:require(replacement is None,'INVALID_INPUT','Only superseded records have a replacement')
    old=r.get('state_change') or {}
    previous={'lifecycle':r['lifecycle'],'reason':old.get('reason',''),'replacement':old.get('replacement')}
    core.c.execute(f'UPDATE {kind}s SET lifecycle=?,state_version=state_version+1,last_event_id=? WHERE project_id=? AND id=?',(to_state,core.event,core.project,ident))
    values=dict(project_id=core.project,id=uid(),kind=kind,record_id=ident,revision=revision,state_version=r['state_version']+1,from_state=r['lifecycle'],to_state=to_state,reason=reason,replacement_id=replacement['id'] if replacement else None,replacement_revision=replacement['revision'] if replacement else None,event_id=core.event,created_at=now())
    records.insert(core.c,'record_state_changes',values)
    return dict(id=ident,kind=kind,revision=revision,state_version=values['state_version'],lifecycle=to_state,previous=previous,state_change=decode(values),validation_changed=False,execution_authorized=False)

def set_state(core,p):
    require(core.principal.method=='native_user_action','USER_ACTION_REQUIRED','Use the native record menu')
    require(isinstance(p['kind'],str) and p['kind'] in STATES,'INVALID_INPUT','Unsupported record kind')
    require(type(p['revision']) is int and type(p['state_version']) is int,'INVALID_INPUT','Integer revision and state version required')
    r=records.get(core.c,core.project,p['kind'],p['id'])
    require(r['revision']==p['revision'] and r['state_version']==p['state_version'] and r['lifecycle']==p['from_state'],'STALE','Record content or state changed')
    require(p['from_state']!=p['to_state'],'INVALID_INPUT','Choose another state')
    return apply(core,p['kind'],p['id'],p['revision'],p['to_state'],reason=p.get('reason',''),replacement=p.get('replacement'))

HANDLERS={'record.set_state':set_state}
