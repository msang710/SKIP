"""Versioned learning contracts. All authority remains in Core/native user commands."""
import json
from . import records
from .common import uid, now, digest, encoded, identifier, text
from .errors import require

KINDS={'failure','guideline','claim','boundary','environment','obligation','scenario'}
FIELDS={
 'failure':({'title','expected','actual','conditions','impact','cause','cause_state','state'},set()),
 'guideline':({'title','conditions','action','verification','state','targets'},set()),
 'claim':({'title','statement','assumptions','limitations'},set()),
 'boundary':({'title','description'},set()),
 'environment':({'title','requirements'},set()),
 'obligation':({'title','expected','acceptance','phase','required'},{'surfaces'}),
 'scenario':({'title','kind','trigger','invariant','oracle','cleanup','fault'},set()),
}
LINK_ROLES={
 'failure':{},'boundary':{},'environment':{},
 'guideline':{'failure':'failure','supersedes':'guideline'},
 'claim':{'guideline':'guideline'},
 'obligation':{'claim':'claim','boundary':'boundary','environment':'environment','dependency':'obligation','guideline':'guideline'},
 'scenario':{'obligation':'obligation'},
}

def get(core,kind,ident,revision=None):
    require(kind in KINDS,'INVALID_INPUT','Unknown learning kind')
    row=core.c.execute('SELECT v.*,h.current_revision FROM learning_records h JOIN learning_versions v ON v.project_id=h.project_id AND v.kind=h.kind AND v.id=h.id AND v.revision=COALESCE(?,h.current_revision) WHERE h.project_id=? AND h.kind=? AND h.id=?',
                       (revision,core.project,kind,ident)).fetchone()
    require(row is not None,'NOT_FOUND','Learning record unavailable')
    value=dict(row);value['body']=json.loads(value.pop('body_json'))
    value['links']=[dict(r) for r in core.c.execute('SELECT role,target_kind kind,target_id id,target_revision revision FROM learning_links WHERE project_id=? AND owner_kind=? AND owner_id=? AND owner_revision=? ORDER BY role,target_id',(core.project,kind,ident,value['revision']))]
    value['evidence']=[dict(r) for r in core.c.execute('SELECT evidence_id id,role FROM learning_evidence WHERE project_id=? AND kind=? AND id=? AND revision=?',(core.project,kind,ident,value['revision']))]
    value['accepted']=bool(core.c.execute('SELECT 1 FROM learning_acceptances WHERE project_id=? AND kind=? AND id=? AND revision=?',(core.project,kind,ident,value['revision'])).fetchone())
    scope=core.c.execute('SELECT scope_id FROM learning_scopes WHERE project_id=? AND kind=? AND id=? AND revision=?',(core.project,kind,ident,value['revision'])).fetchone()
    value['scope_id']=scope['scope_id'] if scope else None
    if kind=='failure':
        value['occurrences']=[dict(r) for r in core.c.execute('SELECT * FROM failure_occurrences WHERE project_id=? AND case_id=? ORDER BY created_at DESC,id LIMIT 31',(core.project,ident))]
        value['attempts']=[dict(r) for r in core.c.execute('SELECT * FROM failure_attempts WHERE project_id=? AND case_id=? ORDER BY created_at DESC,id LIMIT 31',(core.project,ident))]
        value['history_complete']=len(value['occurrences'])<=30 and len(value['attempts'])<=30
        value['occurrences']=value['occurrences'][:30];value['attempts']=value['attempts'][:30]
    return value

def validate(kind,body):
    require(isinstance(body,dict) and FIELDS[kind][0]<=set(body)<=FIELDS[kind][0]|FIELDS[kind][1],'INVALID_INPUT','Invalid learning fields')
    for k,v in body.items():
        if k not in ('targets','requirements','fault','required','surfaces'):text(v)
    if kind=='failure':
        require(body['cause_state'] in ('unknown','hypothesis','confirmed') and body['state'] in ('investigating','mitigated','resolved'),'INVALID_INPUT','Invalid failure state')
    if kind=='guideline':
        require(body['state'] in ('active','retired','superseded'),'INVALID_INPUT','Invalid guideline lifecycle')
        require(isinstance(body['targets'],list) and 0<len(body['targets'])<=64,'INVALID_INPUT','Explicit guideline targets required')
        for t in body['targets']:
            require(isinstance(t,dict) and set(t)=={'source_id','path'},'INVALID_INPUT','Invalid target')
            identifier(t['source_id']); path=t['path']
            require(isinstance(path,str) and path and not path.startswith(('/','\\')) and '\\' not in path and ':' not in path and '..' not in path.split('/'),'INVALID_INPUT','Target must be portable')
    if kind=='environment':
        require(isinstance(body['requirements'],dict) and 0<len(body['requirements'])<=64,'INVALID_INPUT','Environment requirements required')
        for k,v in body['requirements'].items():
            identifier(k);require(isinstance(v,dict) and set(v)=={'op','value'} and v['op'] in ('eq','in','gte','lte'),'INVALID_INPUT','Unknown comparison')
            require(v['op']!='in' or isinstance(v['value'],list),'INVALID_INPUT','Set expected')
            require(v['op'] not in ('gte','lte') or type(v['value']) in (int,float),'INVALID_INPUT','Numeric bound required')
    if kind=='obligation':
        if 'surfaces' in body:
            require(isinstance(body['surfaces'],list) and body['surfaces'] and all(v in ('unit','integration','typecheck','build','package','install','runtime','ui','device','production') for v in body['surfaces']),'INVALID_INPUT','Invalid verification surfaces')
        require(body['phase'] in ('before_implementation','before_deploy','after_deploy','report_only') and type(body['required']) is bool,'INVALID_INPUT','Invalid obligation phase')
    if kind=='scenario':
        require(body['kind'] in ('normal','boundary','fault','concurrency','recovery'),'INVALID_INPUT','Invalid scenario')
        f=body['fault'];require(f is None or isinstance(f,dict) and set(f)=={'mode','target','kind','probability','seed','schedule'},'INVALID_INPUT','Invalid fault spec')
        if f:
            require(f['mode'] in ('random','forced'),'INVALID_INPUT','Invalid fault mode')
            for k in ('target','kind','schedule'):text(f[k])
            require(type(f['probability']) in (int,float) and 0<=f['probability']<=1,'INVALID_INPUT','Invalid probability')
            require(f['seed'] is None or type(f['seed']) is int,'INVALID_INPUT','Invalid seed')
        require(body['kind']!='fault' or f is not None,'INVALID_INPUT','Fault specification required')

def propose(core,p):
    kind=p['kind'];require(kind in KINDS,'INVALID_INPUT','Unknown kind');validate(kind,p['body'])
    ident=identifier(p.get('id') or uid());rev=p['expected_revision'];require(type(rev) is int and rev>=0,'INVALID_INPUT','Invalid revision')
    old=core.c.execute('SELECT current_revision FROM learning_records WHERE project_id=? AND kind=? AND id=?',(core.project,kind,ident)).fetchone()
    require((old['current_revision'] if old else 0)==rev,'STALE','Learning record changed')
    links=p.get('links',[]);require(isinstance(links,list) and len(links)<=128,'INVALID_INPUT','Too many links')
    goal=p.get('goal_id');g=records.get(core.c,core.project,'goal',goal) if goal else None
    for link in links:
        require(isinstance(link,dict) and set(link)=={'role','kind','id','revision'} and LINK_ROLES[kind].get(link['role'])==link['kind'],'INVALID_INPUT','Invalid typed link')
        target=get(core,link['kind'],link['id'],link['revision'])
        require(target['current_revision']==link['revision'],'STALE','Referenced version changed')
        require(target['goal_id'] is None or target['goal_id']==goal,'PROJECT_MISMATCH','Related record belongs to another goal')
        require(not(kind==link['kind'] and ident==link['id']),'INVALID_INPUT','Self reference')
    for role in ({'claim','boundary','environment'} if kind=='obligation' else {'obligation'} if kind=='scenario' else set()):
        require(sum(l['role']==role for l in links)==1,'INVALID_INPUT','Required relation missing')
    if kind=='obligation':
        def visit(oid,revision,seen):
            require(oid!=ident and len(seen)<128,'INVALID_INPUT','Cyclic or oversized obligation graph')
            if (oid,revision) in seen:return
            seen.add((oid,revision))
            for l in get(core,'obligation',oid,revision)['links']:
                if l['role']=='dependency':visit(l['id'],l['revision'],seen)
        for l in links:
            if l['role']=='dependency':visit(l['id'],l['revision'],set())
    evidence=p.get('evidence',[])
    require(isinstance(evidence,list) and len(evidence)<=64,'INVALID_INPUT','Bounded evidence links required')
    for e in evidence:
        require(set(e)=={'id','role'},'INVALID_INPUT','Invalid evidence reference')
        identifier(e['role']);ev=core.one('evidence',e['id'])
        require(ev['sealed_at'] and ev['result'] not in ('NOT_RUN','INCONCLUSIVE'),'INVALID_INPUT','Observed evidence required')
    if kind=='failure' and (p['body']['cause_state']=='confirmed' or p['body']['state']=='resolved'):
        require(evidence,'INVALID_INPUT','Cause confirmation or resolution needs evidence')
    if kind=='guideline' and p['body']['state']!='active':require(evidence,'INVALID_INPUT','Retirement needs evidence')
    snapshot=None
    if kind=='claim':
        from .execution import verify_snapshot
        require(p.get('snapshot_id'),'INVALID_INPUT','Claim requires an observed source scope')
        snapshot=verify_snapshot(core,p['snapshot_id'])
        require(core.one('scopes',snapshot['scope_id'])['goal_id']==goal,'PROJECT_MISMATCH','Claim source scope outside goal')
    if not old:records.insert(core.c,'learning_records',dict(project_id=core.project,kind=kind,id=ident,current_revision=0))
    records.insert(core.c,'learning_versions',dict(project_id=core.project,kind=kind,id=ident,revision=rev+1,goal_id=goal,goal_revision=g['revision'] if g else None,body_json=encoded(p['body']),digest=digest([p['body'],links]),event_id=core.event,created_at=now()))
    for l in links:records.insert(core.c,'learning_links',dict(project_id=core.project,owner_kind=kind,owner_id=ident,owner_revision=rev+1,role=l['role'],target_kind=l['kind'],target_id=l['id'],target_revision=l['revision']))
    if snapshot:records.insert(core.c,'learning_scopes',dict(project_id=core.project,kind=kind,id=ident,revision=rev+1,scope_id=snapshot['scope_id']))
    for e in evidence:records.insert(core.c,'learning_evidence',dict(project_id=core.project,kind=kind,id=ident,revision=rev+1,evidence_id=e['id'],role=e['role']))
    core.c.execute('UPDATE learning_records SET current_revision=? WHERE project_id=? AND kind=? AND id=?',(rev+1,core.project,kind,ident))
    return get(core,kind,ident)

def accept(core,p):
    require(p['kind'] in ('claim','guideline','obligation'),'INVALID_INPUT','Not an enforceable contract')
    r=get(core,p['kind'],p['id'],p['revision']);require(r['current_revision']==p['revision'],'STALE','Contract changed')
    from .execution import current_selection
    selection=current_selection(core,p['selection_id'])
    decision=records.get(core.c,core.project,'decision',selection['decision_id'])
    require(r['goal_id'] is None or decision['goal_id']==r['goal_id'],'PROJECT_MISMATCH','Decision outside contract goal')
    if r['kind']=='guideline' and r['body']['state']=='superseded':require(any(l['role']=='supersedes' for l in r['links']),'INVALID_INPUT','Replacement relation required')
    records.insert(core.c,'learning_acceptances',dict(project_id=core.project,kind=r['kind'],id=r['id'],revision=r['revision'],selection_id=selection['id'],contract_digest=contract_digest(core,r),event_id=core.event))
    return get(core,r['kind'],r['id'])

def listing(core,kind,goal=None,limit=30,offset=0):
    require(kind in KINDS,'INVALID_INPUT','Unknown kind')
    rows=core.c.execute('SELECT h.id FROM learning_records h JOIN learning_versions v ON v.project_id=h.project_id AND v.kind=h.kind AND v.id=h.id AND v.revision=h.current_revision WHERE h.project_id=? AND h.kind=? AND (? IS NULL OR v.goal_id=? OR v.goal_id IS NULL) ORDER BY (SELECT sequence FROM events e WHERE e.project_id=v.project_id AND e.id=v.event_id) DESC,h.id LIMIT ? OFFSET ?', (core.project,kind,goal,goal,limit,offset))
    return [get(core,kind,r['id']) for r in rows]


def contract_digest(core,row):
    parts=[row['digest']]
    if row['kind']=='claim':
        # Include every current obligation and scenario that implements this claim.
        from .assurance import obligations
        for obligation in obligations(core,row):
            parts.append((obligation['id'],obligation['revision'],obligation['digest']))
            for l in obligation['links']:
                target=get(core,l['kind'],l['id'],l['revision'])
                parts.append((l,target['current_revision'],target['digest']))
            scenarios=core.c.execute("SELECT h.id FROM learning_records h JOIN learning_links l ON l.project_id=h.project_id AND l.owner_kind=h.kind AND l.owner_id=h.id AND l.owner_revision=h.current_revision WHERE h.project_id=? AND h.kind='scenario' AND l.role='obligation' AND l.target_id=? AND l.target_revision=? ORDER BY h.id",(core.project,obligation['id'],obligation['revision']))
            for s in scenarios:
                scenario=get(core,'scenario',s['id']);parts.append((scenario['id'],scenario['revision'],scenario['digest']))
    return digest(parts)
