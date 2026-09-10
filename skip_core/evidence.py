import hashlib
from . import records
from .common import now, text, uid
from .errors import require
from .execution import paths, verify_snapshot

SURFACES={'source','unit','integration','typecheck','build','package','install','runtime','ui','device','production'}
RESULTS={'PASS','FAIL','NOT_RUN','INCONCLUSIVE'}


def record(core,p):
    require(p['surface'] in SURFACES and p['result'] in RESULTS,'INVALID_INPUT','Invalid verification surface or result')
    saved=core.one('snapshots',p['snapshot_id'])
    if p['result']!='NOT_RUN':
        verify_snapshot(core,saved['id'])
    x=core.one('executions',p['execution_id']) if p.get('execution_id') else None
    if x:
        auth=core.one('authorizations',x['authorization_id'])
        actual={(v['source_id'],v['relative_path']) for v in paths(core,saved['scope_id'])}
        authorized={(v['source_id'],v['relative_path']) for v in paths(core,auth['scope_id'])}
        require(actual==authorized,'INVALID_INPUT','Evidence must cover the executed source scope')
    require(not p.get('checks') or x is not None,'INVALID_INPUT','Work checks require an execution')
    ident=uid()
    provenance={'agent':'agent_report','human':'user_observation','system':'host_observation'}[core.principal.kind]
    records.insert(core.c,'evidence',dict(project_id=core.project,id=ident,snapshot_id=saved['id'],execution_id=x['id'] if x else None,
        reporter_interaction_id=core.interaction,surface=p['surface'],result=p['result'],provenance=provenance,
        summary=text(p['summary']),method=text(p['method']),observed_at=now() if p['result']!='NOT_RUN' else None,
        event_id=core.event,created_at=now()))
    for check in p.get('checks',[]):
        require(set(check)=={'check_id','verdict','explanation'} and check['verdict'] in RESULTS,'INVALID_INPUT','Invalid check result')
        require(check['verdict']==p['result'],'INVALID_INPUT','Check verdict conflicts with evidence')
        expected=core.c.execute('SELECT surface FROM work_checks WHERE project_id=? AND work_item_id=? AND work_revision=? AND check_id=?',
                               (core.project,x['work_item_id'],x['work_revision'],check['check_id'])).fetchone()
        require(expected and expected['surface']==p['surface'],'INVALID_INPUT','Verification surface differs from required check')
        records.insert(core.c,'work_check_results',dict(project_id=core.project,evidence_id=ident,
            work_item_id=x['work_item_id'],work_revision=x['work_revision'],**check))
    for criterion in p.get('criteria',[]):
        require(set(criterion)=={'requirement_id','requirement_revision','criterion_id','verdict','explanation'}
                and criterion['verdict']==p['result'],'INVALID_INPUT','Invalid criterion result')
        records.insert(core.c,'criterion_results',dict(project_id=core.project,evidence_id=ident,**criterion))
    if p.get('payload'):
        payload=p['payload']
        require(set(payload)=={'media_type','text'},'INVALID_INPUT','Invalid evidence payload')
        content=text(payload['text'],256000).encode()
        records.insert(core.c,'evidence_payloads',dict(project_id=core.project,evidence_id=ident,part_id='output',
            media_type=text(payload['media_type'],128),content=content,content_digest=hashlib.sha256(content).hexdigest(),byte_length=len(content)))
    core.c.execute('UPDATE evidence SET sealed_at=? WHERE project_id=? AND id=?',(now(),core.project,ident))
    return {'evidence_id':ident,'snapshot_id':saved['id'],'result':p['result'],'surface':p['surface'],'provenance':provenance}
