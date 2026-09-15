"""Interpret a verified input before a goal exists; materialize records, not authority."""
import json
from . import records
from .common import digest, encoded, identifier, now, text, uid
from .errors import require
from .input_contract import classify

OPS = {'entry.submit': ({'input_id','input_digest','expected_revision','body','target','records'}, set(), False)}


def lookup(core, input_id):
    identifier(input_id)
    row = core.c.execute('SELECT * FROM input_envelopes WHERE project_id=? AND input_id=?', (core.project,input_id)).fetchone()
    require(row is not None, 'NOT_FOUND', 'Exact input unavailable; use native entry to capture the actual user turn')
    envelope = json.loads(row['body_json'])
    return row, envelope


def inspect(core, input_id):
    row, envelope = lookup(core,input_id)
    from .request_intent import resolve
    version=resolve(core,input_id)
    linked = core.c.execute('SELECT request_id,goal_id FROM input_materializations WHERE project_id=? AND input_id=?', (core.project,input_id)).fetchone()
    suggestion = classify(envelope)
    return {'input_id':input_id,'input':envelope,'provenance':row['verification'],
            'interpretation':version,
            'suggestion':suggestion,'authoring_base':dict(linked) if linked else None,
            'next_action':'use_authoring_base' if linked else 'interpret_input',
            'next_tool':'skip_submit' if linked else 'skip_enter',
            'authority':'reading_material'}


def propose(core, p):
    from .entry_runtime import validate_body
    row, envelope = lookup(core,p['input_id'])
    require(p['input_digest']==row['digest'], 'STALE', 'Input digest changed')
    validate_body(core,p['body'],envelope)
    require(not core.c.execute('SELECT 1 FROM input_materializations WHERE project_id=? AND input_id=?',(core.project,p['input_id'])).fetchone(), 'CONFLICT', 'Input already materialized; interpret the linked request instead')
    from .request_intent import write
    return {'input_id':p['input_id'],**write(core,p['input_id'],p['body'],p['expected_revision'])}


def submit(core, p):
    from .authoring import submit as submit_records, receipt
    row,envelope=lookup(core,p['input_id'])
    require(row['digest']==p['input_digest'],'STALE','Input digest changed')
    old=core.c.execute('SELECT * FROM input_materializations WHERE project_id=? AND input_id=?',(core.project,p['input_id'])).fetchone()
    if old:
        require(old['payload_digest']==digest(p),'CONFLICT','Input already materialized with different content; use its authoring_base')
        return json.loads(old['receipt_json'])
    target=p['target'];items=p['records'];body=p['body']
    require(isinstance(target,dict) and target.get('mode') in ('create','existing','none'),'INVALID_INPUT','Choose create, existing or none target')
    require(isinstance(items,list) and len(items)<=64,'INVALID_INPUT','Bounded records array required')
    # Proposal validation is reused. No human Principal is constructed here.
    interpretation=propose(core,{k:p[k] for k in ('input_id','input_digest','expected_revision','body')})
    acts=set(body['acts'])
    if target['mode']=='none':
        require(set(target)=={'mode'} and not items,'INVALID_INPUT','No-target interpretation cannot write records')
        return {**interpretation,'committed':True,'records':[], 'next_action':'resolve_meaning' if body['unresolved'] or 'unresolved' in acts else 'answer' if acts <= {'answer','cancel'} else 'select_target','goal_created':False}
    require(not body['unresolved'] and 'unresolved' not in acts,'AMBIGUOUS_INPUT','Resolve meaning before materializing records')
    require(acts & {'create_goal','record','requirements','design','tasks','decide','investigate','implement','validate','deploy'},'INVALID_INPUT','Interpretation does not request records')
    verified=core.c.execute('SELECT 1 FROM verified_interactions WHERE project_id=? AND interaction_id=?',(core.project,p['input_id'])).fetchone()
    require(row['verification']=='verified' and verified,'PROVENANCE_UNAVAILABLE','Unverified input may be proposed but cannot create a user request')
    if target['mode']=='create':
        require(set(target)=={'mode','fields'} and 'create_goal' in acts,'INVALID_INPUT','New goal needs explicit create_goal interpretation and goal fields')
        require(not body['targets'],'CONFLICT','Selected records need their existing goal; do not silently copy them into a new goal')
        fields=target['fields']
        require(isinstance(fields,dict) and set(fields)==set(records.FIELDS['goal']),'INVALID_INPUT','Goal requires title, intent and success_definition')
        goal=None
    else:
        require(set(target)=={'mode','goal_id','revision'} and type(target['revision']) is int and target['revision']>0 and 'create_goal' not in acts,'INVALID_INPUT','Existing target requires exact goal revision')
        goal=records.get(core.c,core.project,'goal',target['goal_id'],target['revision'])
        require(goal['revision']==goal['current_revision'] and goal['lifecycle']=='active','STALE','Goal changed')
        for ref in body['targets']:
            r=records.get(core.c,core.project,ref['kind'],ref['id'],ref['revision'])
            require(r['goal_id']==goal['id'],'PROJECT_MISMATCH','Selected record belongs to another goal')
    allowed={'record':{'decision','requirement','plan','work_item'},'decide':{'decision'},'requirements':{'requirement'},'design':{'plan'},'tasks':{'work_item'},'implement':{'work_item'},'investigate':set(),'validate':set(),'deploy':{'work_item'},'create_goal':set()}
    kinds=set().union(*(allowed.get(a,set()) for a in acts))
    require(all(isinstance(i,dict) and i.get('kind') in kinds for i in items),'INVALID_INPUT','Record kinds exceed interpreted request; do not turn goal creation into a plan')
    original=core.c.execute('SELECT body FROM interactions WHERE project_id=? AND id=?',(core.project,p['input_id'])).fetchone()['body']
    request=core.c.execute('SELECT * FROM requests WHERE project_id=? AND interaction_id=?',(core.project,p['input_id'])).fetchone()
    if request:
        require(goal is not None and core.c.execute('SELECT 1 FROM request_goals WHERE project_id=? AND request_id=? AND goal_id=?',(core.project,request['id'],goal['id'])).fetchone(),'CONFLICT','Input already belongs to another request goal')
        request_id=request['id']
    else:
        request_id=uid()
        records.insert(core.c,'requests',dict(project_id=core.project,id=request_id,interaction_id=p['input_id'],operation='record',intent=text(original),intent_digest=digest(original),created_at=now()))
    if goal is None:
        ident,rev=records.publish(core.c,core.project,{'kind':'goal','request_id':request_id,'expected_revision':0,'fields':fields,'children':{}},core.event,allow_new_goal=True)
        records.advance(core.c,core.project,'goal',ident,rev,core.event_record('record.published'))
        goal=records.get(core.c,core.project,'goal',ident,rev)
    if not core.c.execute('SELECT 1 FROM request_goals WHERE project_id=? AND request_id=? AND goal_id=?',(core.project,request_id,goal['id'])).fetchone():
        records.insert(core.c,'request_goals',dict(project_id=core.project,request_id=request_id,goal_id=goal['id']))
    # Request queries resolve the original input directly; no semantic copy.
    base={'goal_id':goal['id'],'request_id':request_id}
    result=submit_records(core,{'base':base,'records':items}) if items else receipt([])
    result.update(authoring_base=base,goal=goal,goal_created=target['mode']=='create',input_id=p['input_id'],interpretation_revision=interpretation['revision'])
    records.insert(core.c,'input_materializations',dict(project_id=core.project,input_id=p['input_id'],revision=interpretation['revision'],request_id=request_id,goal_id=goal['id'],payload_digest=digest(p),receipt_json=encoded(result)))
    return result

HANDLERS={'entry.submit':submit}
