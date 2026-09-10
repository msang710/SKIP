"""Portable input/intent history and read-only stage assessment."""
import json
from . import records
from .common import digest,encoded,uid
from .errors import require
from .input_contract import normalize,classify,ACTS,OUTPUTS

OPS={
 'input.ingest':(set(),set(),True),
 'intent.propose':({'request_id','expected_revision','body'},set(),False),
 'action.propose':({'request_id','body'},{'id','expected_revision'},False),
 'response.bind':({'proposal_id','revision'},set(),True),
}

def ingest(core,p):
    core.principal.human()
    old=core.c.execute('SELECT * FROM input_envelopes WHERE project_id=? AND input_id=?',(core.project,core.interaction)).fetchone()
    if old:return {'input_id':old['input_id'],'digest':old['digest']}
    body=normalize(core.principal.user_text,core.project)
    route={'host_user_turn':'host_message','native_user_action':'native_ui','interactive_tty':'host_message'}[core.principal.method]
    body.update(adapter_id=core.principal.verifier,verification='verified',route=route)
    records.insert(core.c,'input_envelopes',dict(project_id=core.project,input_id=core.interaction,route=route,verification='verified',body_json=encoded(body),digest=body['digest'],event_id=core.event))
    return {'input_id':core.interaction,'digest':body['digest']}

def input_for(core,request):
    r=core.one('requests',request)
    row=core.c.execute('SELECT * FROM input_envelopes WHERE project_id=? AND input_id=?',(core.project,r['interaction_id'])).fetchone()
    return r,json.loads(row['body_json']) if row else None

def validate_body(core,body,envelope):
    require(isinstance(body,dict) and set(body)=={'acts','constraints','targets','evidence_spans','unresolved'},'INVALID_INPUT','Invalid interpretation')
    require(isinstance(body['acts'],list) and 0<len(body['acts'])<=12 and all(a in ACTS for a in body['acts']),'INVALID_INPUT','Unknown requested action')
    require(isinstance(body['constraints'],list) and all(c in ('implement','deploy','design_change') for c in body['constraints']),'INVALID_INPUT','Unknown constraint')
    require(isinstance(body['unresolved'],list) and len(body['unresolved'])<=30 and all(isinstance(v,str) for v in body['unresolved']),'INVALID_INPUT','Unresolved reasons required')
    require(set(classify(envelope)['constraints'])<=set(body['constraints']),'CONFLICT','Cannot discard explicit input prohibitions')
    require(not set(body['acts']) & set(body['constraints']),'CONFLICT','Request conflicts with prohibition')
    require(not ('design' in body['acts'] and 'design_change' in body['constraints']),'CONFLICT','Design change prohibited')
    require(isinstance(body['targets'],list) and len(body['targets'])<=20,'INVALID_INPUT','Bounded targets required')
    for ref in body['targets']:
        require(isinstance(ref,dict) and set(ref)=={'kind','id','revision'},'INVALID_INPUT','Exact target required')
        r=records.get(core.c,core.project,ref['kind'],ref['id'],ref['revision'])
        require(r['revision']==r['current_revision'],'STALE','Selected target changed')
    require(all(ref in body['targets'] for ref in envelope['targets']),'CONFLICT','Cannot drop explicit selected record')
    require(isinstance(body['evidence_spans'],list) and len(body['evidence_spans'])<=100,'INVALID_INPUT','Bounded spans required')
    for span in body['evidence_spans']:
        require(isinstance(span,dict) and set(span)=={'part_id','start','end'},'INVALID_INPUT','Invalid evidence span')
        part=next((p for p in envelope['parts'] if p['part_id']==span['part_id']),None)
        require(part is not None and part['role']=='user_instruction' and type(span['start']) is int and type(span['end']) is int and part['start']<=span['start']<span['end']<=part['end'],'INVALID_INPUT','Instruction must cite an actual instruction part')
    require(body['acts']==['answer'] or body['evidence_spans'],'INVALID_INPUT','Action lacks instruction evidence')

def propose(core,p):
    request,envelope=input_for(core,p['request_id'])
    require(envelope is not None,'PROVENANCE_UNAVAILABLE','Legacy request has no typed input; do not invent host provenance')
    body=p['body'];validate_body(core,body,envelope)
    for ref in body['targets']:
        r=records.get(core.c,core.project,ref['kind'],ref['id'],ref['revision'])
        require(core.c.execute('SELECT 1 FROM request_goals WHERE project_id=? AND request_id=? AND goal_id=?',(core.project,p['request_id'],r['goal_id'])).fetchone(),'PROJECT_MISMATCH','Target is outside request goal')
    head=core.c.execute('SELECT COALESCE(max(revision),0) FROM intent_interpretations WHERE project_id=? AND request_id=?',(core.project,p['request_id'])).fetchone()[0]
    require(type(p['expected_revision']) is int and head==p['expected_revision'],'STALE','Interpretation changed')
    records.insert(core.c,'intent_interpretations',dict(project_id=core.project,request_id=p['request_id'],revision=head+1,input_id=request['interaction_id'],body_json=encoded(body),digest=digest(body),event_id=core.event))
    return {'request_id':p['request_id'],'revision':head+1,'digest':digest(body),'authority':'interpretation_only'}

def inspect(core,p):
    request,envelope=input_for(core,p['request_id'])
    row=core.c.execute('SELECT * FROM intent_interpretations WHERE project_id=? AND request_id=? ORDER BY revision DESC LIMIT 1',(core.project,p['request_id'])).fetchone()
    return {'request_id':request['id'],'input':envelope,'provenance':'verified' if envelope else 'legacy_unknown','interpretation':{'revision':row['revision'],'digest':row['digest'],'body':json.loads(row['body_json'])} if row else None,'authority':'reading_material'}

def assess(core,p):
    entry=inspect(core,p);interpretation=entry['interpretation'];goals=[r[0] for r in core.c.execute('SELECT goal_id FROM request_goals WHERE project_id=? AND request_id=?',(core.project,p['request_id']))]
    goal=p.get('goal_id');require(goal in goals if goal else len(goals)==1,'AMBIGUOUS_INPUT','Specify an exact request goal')
    goal=goal or goals[0];reasons=[];missing=[];unresolved=[];basis=[entry,core.policy_digest()]
    body=interpretation['body'] if interpretation else {'acts':['answer'],'constraints':[],'targets':[],'unresolved':['interpretation_missing']}
    reasons.extend(body['unresolved'])
    for ref in body['targets']:
        r=records.get(core.c,core.project,ref['kind'],ref['id'],ref['revision']);basis.append([r['digest'],r['current_revision']])
        if r['current_revision']!=ref['revision']:reasons.append('target_stale')
    outputs=list(dict.fromkeys(out for a in body['acts'] for out in OUTPUTS[a]))
    # Read only goal-local heads. Truncation is explicit, never absence.
    counts={};heads={}
    for kind in ('decision','requirement','plan','work_item'):
        ids=core.c.execute(f"SELECT id FROM {kind}s WHERE project_id=? AND goal_id=? AND lifecycle='active' ORDER BY id LIMIT 101",(core.project,goal)).fetchall()
        if len(ids)>100:reasons.append('records_incomplete')
        heads[kind]=[records.get(core.c,core.project,kind,r['id']) for r in ids[:100]];counts[kind]=len(ids)
        basis.extend([r['id'],r['revision'],r['digest']] for r in heads[kind])
    from .decision_state import attach
    for d in heads['decision']:
        state=attach(core,d);basis.append(state)
        if not state.get('selection') or state.get('selection_state')!='selected':unresolved.append(d['id'])
    if 'tasks' in body['acts'] and not counts['plan']:missing.append('plan')
    if set(body['acts']) & {'implement','deploy'} and not counts['work_item']:missing.append('work_item')
    output_records={}
    for kind in outputs:
        if kind not in heads:continue
        ids={r[0] for r in core.c.execute(f'SELECT id FROM {kind}s WHERE project_id=? AND origin_request_id=?',(core.project,p['request_id']))}
        produced=[r for r in heads[kind] if r['id'] in ids]
        if kind=='work_item':
            valid=[]
            for work in produced:
                links=work['children']['plan_items']
                if not links or not work['children']['checks']:continue
                if any(not any(link['plan_id']==t['id'] and link['plan_revision']==t['revision'] for link in links) for t in body['targets'] if t['kind']=='plan'):continue
                valid.append(work)
            produced=valid
        output_records[kind]=[{'id':r['id'],'revision':r['revision']} for r in produced]
    eligibility='not_requested'
    if set(body['acts']) & {'implement','deploy','resume'}:
        eligibility='requires_native_execution_check'
        if reasons or missing:eligibility='preparation_needed'
    return {'request_id':p['request_id'],'goal_id':goal,'interpretation_revision':interpretation['revision'] if interpretation else None,'requested_actions':body['acts'],'constraints':body['constraints'],'allowed_preparation':['investigate'],'required_outputs':outputs,'output_records':output_records,'missing_artifacts':missing,'unresolved_product_decisions':unresolved,'execution_eligibility':eligibility,'reasons':reasons,'complete':'records_incomplete' not in reasons,'basis_digest':digest(basis),'authority':'assessment_not_approval'}

def action_propose(core,p):
    request=core.one('requests',p['request_id']);body=p['body']
    require(isinstance(body,dict) and set(body)=={'action','target','scope_digest','constraints'},'INVALID_INPUT','Exact action proposal required')
    require(isinstance(body['target'],dict) and set(body['target'])=={'kind','id','revision'},'INVALID_INPUT','Exact proposal target required')
    require(body['action'] in ACTS and isinstance(body['scope_digest'],str) and len(body['scope_digest'])==64 and isinstance(body['constraints'],list),'INVALID_INPUT','Invalid action basis')
    r=records.get(core.c,core.project,body['target']['kind'],body['target']['id'],body['target']['revision'])
    require(r['revision']==r['current_revision'],'STALE','Proposal target changed')
    require(core.c.execute('SELECT 1 FROM request_goals WHERE project_id=? AND request_id=? AND goal_id=?',(core.project,request['id'],r['goal_id'])).fetchone(),'PROJECT_MISMATCH','Proposal outside request')
    ident=p.get('id') or uid();head=core.c.execute('SELECT COALESCE(max(revision),0) FROM action_proposals WHERE project_id=? AND id=?',(core.project,ident)).fetchone()[0]
    require(head==p.get('expected_revision',0),'STALE','Proposal changed')
    records.insert(core.c,'action_proposals',dict(project_id=core.project,id=ident,revision=head+1,request_id=request['id'],body_json=encoded(body),digest=digest(body),event_id=core.event))
    return {'id':ident,'revision':head+1,'digest':digest(body),'display_ref':f'SKIP-PROPOSAL:{ident}:{head+1}:{digest(body)}','authority':'proposal_only'}

def bind(core,p):
    # Binding requires a native adapter-verified exact reply, never guessed from words.
    proof=getattr(core.principal,'response_ref',None)
    require(proof==(p['proposal_id'],p['revision']),'USER_ACTION_REQUIRED','Host must verify the exact proposal reply')
    row=core.c.execute('SELECT * FROM action_proposals WHERE project_id=? AND id=? ORDER BY revision DESC LIMIT 1',(core.project,p['proposal_id'])).fetchone()
    require(row and row['revision']==p['revision'],'STALE','Proposal changed')
    body=json.loads(row['body_json']);r=records.get(core.c,core.project,**{'kind':body['target']['kind'],'ident':body['target']['id'],'revision':body['target']['revision']})
    require(r['revision']==r['current_revision'],'STALE','Proposal target changed')
    require(core.context is not None,'CONTEXT_EXPIRED','Current host context required')
    core.context.check()
    ingest(core,{})
    records.insert(core.c,'response_bindings',dict(project_id=core.project,input_id=core.interaction,proposal_id=row['id'],proposal_revision=row['revision'],basis_digest=row['digest'],event_id=core.event))
    return {'input_id':core.interaction,'proposal_id':row['id'],'revision':row['revision'],'authority':'exact_response_only'}

HANDLERS={'input.ingest':ingest,'intent.propose':propose,'action.propose':action_propose,'response.bind':bind}
