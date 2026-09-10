"""Portable scope matching and current, evidence-backed guideline assessments."""
from . import records,learning
from .common import uid,now,digest,text,encoded
from .errors import require,CoreError
from .execution import verify_snapshot,paths

def overlaps(a,b):
    return a=='.' or b=='.' or a==b or a.startswith(b.rstrip('/')+'/') or b.startswith(a.rstrip('/')+'/')

def candidates(core,goal,snapshot_id=None):
    scope_paths=paths(core,core.one('snapshots',snapshot_id)['scope_id']) if snapshot_id else None
    if scope_paths:
        ids=core.c.execute("""SELECT DISTINCT h.id FROM learning_records h JOIN learning_versions v ON v.project_id=h.project_id AND v.kind=h.kind AND v.id=h.id AND (v.revision=h.current_revision OR EXISTS(SELECT 1 FROM learning_acceptances a WHERE a.project_id=v.project_id AND a.kind=v.kind AND a.id=v.id AND a.revision=v.revision))
            WHERE h.project_id=? AND h.kind='guideline' AND (v.goal_id=? OR EXISTS(
              SELECT 1 FROM json_each(v.body_json,'$.targets') t,json_each(?) p
              WHERE json_extract(t.value,'$.source_id')=json_extract(p.value,'$.source_id') AND (
                json_extract(t.value,'$.path')='.' OR json_extract(p.value,'$.relative_path')='.' OR
                json_extract(t.value,'$.path')=json_extract(p.value,'$.relative_path') OR
                substr(json_extract(t.value,'$.path'),1,length(json_extract(p.value,'$.relative_path'))+1)=json_extract(p.value,'$.relative_path')||'/' OR
                substr(json_extract(p.value,'$.relative_path'),1,length(json_extract(t.value,'$.path'))+1)=json_extract(t.value,'$.path')||'/')))
            ORDER BY h.id LIMIT 1001""",(core.project,goal,encoded(scope_paths))).fetchall()
        rows=[learning.get(core,'guideline',r['id']) for r in ids]
    else:
        rows=learning.listing(core,'guideline',None,1001)
    items=[]
    for row in rows[:1000]:
        explicit=row['goal_id']==goal
        matches=[t for t in row['body']['targets'] if scope_paths and any(t['source_id']==p['source_id'] and overlaps(t['path'],p['relative_path']) for p in scope_paths)]
        old_match=False
        if scope_paths and not explicit and not matches:
            accepted=core.c.execute("SELECT revision FROM learning_acceptances WHERE project_id=? AND kind='guideline' AND id=? ORDER BY revision DESC LIMIT 1",(core.project,row['id'])).fetchone()
            if accepted:
                previous=learning.get(core,'guideline',row['id'],accepted['revision'])
                old_match=previous['goal_id']==goal or any(t['source_id']==p['source_id'] and overlaps(t['path'],p['relative_path']) for t in previous['body']['targets'] for p in scope_paths)
        if not scope_paths or explicit or matches or old_match:
            row['match_reason']='explicit_goal' if explicit else 'scope_overlap' if matches else 'accepted_scope_changed' if old_match else 'scope_unknown'
            # Retired proposals never silently remove the previous accepted contract.
            row['retired']=row['accepted'] and row['body']['state'] in ('retired','superseded')
            items.append(row)
    return {'items':items,'complete':len(rows)<=1000,'scope_known':scope_paths is not None,
            'digest':digest([(r['id'],r['revision'],r['digest'],r['accepted']) for r in items])}

def basis_digest(core,guideline,goal,work,snapshot_id):
    g=records.get(core.c,core.project,'goal',goal)
    w=records.get(core.c,core.project,'work_item',work) if work else None
    return digest([guideline['digest'],g['revision'],w['revision'] if w else None,snapshot_id,core.policy_digest(),candidates(core,goal,snapshot_id)['digest']])

def assess(core,p):
    r=learning.get(core,'guideline',p['guideline_id'],p['revision']);require(r['revision']==r['current_revision'],'STALE','Guideline changed')
    g=records.get(core.c,core.project,'goal',p['goal_id']);w=records.get(core.c,core.project,'work_item',p['work_id']) if p.get('work_id') else None
    require(not w or w['goal_id']==g['id'],'PROJECT_MISMATCH','Work outside goal')
    e=core.one('evidence',p['evidence_id']);snapshot=verify_snapshot(core,p['snapshot_id'])
    require(e['snapshot_id']==snapshot['id'] and core.one('scopes',snapshot['scope_id'])['goal_id']==g['id'],'PROJECT_MISMATCH','Assessment evidence scope differs')
    require(p['applicability'] in ('applies','not_applicable','unknown') and p['outcome'] in ('not_tested','reproduced','not_reproduced','inconclusive'),'INVALID_INPUT','Invalid assessment')
    if p['outcome']=='reproduced':require(e['result']=='FAIL','INVALID_INPUT','Reproduction requires failed evidence')
    if p['outcome']=='not_reproduced':require(e['result']=='PASS' and e['surface']!='source','INVALID_INPUT','Non-reproduction requires a test')
    if p['applicability']=='not_applicable':require(e['result'] not in ('NOT_RUN','INCONCLUSIVE'),'INVALID_INPUT','Non-applicability needs observed evidence')
    ident=uid();records.insert(core.c,'guideline_assessments',dict(project_id=core.project,id=ident,guideline_id=r['id'],guideline_revision=r['revision'],goal_id=g['id'],goal_revision=g['revision'],work_id=w['id'] if w else None,work_revision=w['revision'] if w else None,snapshot_id=snapshot['id'],applicability=p['applicability'],outcome=p['outcome'],rationale=text(p['rationale']),evidence_id=e['id'],basis_digest=basis_digest(core,r,g['id'],w['id'] if w else None,snapshot['id']),event_id=core.event,created_at=now()))
    return {'id':ident,'freshness':'current','provenance':e['provenance']}

def projection(core,goal,snapshot_id=None,work_id=None):
    result=candidates(core,goal,snapshot_id)
    for r in result['items']:
        row=core.c.execute('SELECT * FROM guideline_assessments WHERE project_id=? AND guideline_id=? AND goal_id=? AND work_id IS ? ORDER BY (SELECT sequence FROM events e WHERE e.project_id=guideline_assessments.project_id AND e.id=event_id) DESC LIMIT 1',(core.project,r['id'],goal,work_id)).fetchone()
        r['assessment']=dict(row) if row else None
        if row:
            try:verify_snapshot(core,row['snapshot_id']);fresh=row['basis_digest']==basis_digest(core,r,goal,work_id,row['snapshot_id']) and (not snapshot_id or row['snapshot_id']==snapshot_id)
            except (CoreError,OSError):fresh=False
            r['assessment']['freshness']='current' if fresh else 'stale'
    return result
