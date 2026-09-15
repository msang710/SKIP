"""One semantic source for native entry, Core execution and delivery revalidation."""
import json
from . import records
from .common import digest, encoded
from .errors import require, CoreError


def has_table(core,name):
    return core.c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",(name,)).fetchone() is not None


def resolve(core,input_id,*,for_write=False):
    versions=[];semantic=None;latest=-1
    if has_table(core,'input_intent_versions'):
        versions.extend(dict(r) for r in core.c.execute("SELECT v.*,e.sequence,'input' AS source FROM input_intent_versions v JOIN events e ON e.project_id=v.project_id AND e.id=v.event_id WHERE v.project_id=? AND v.input_id=?",(core.project,input_id)))
    if has_table(core,'intent_interpretations'):
        versions.extend(dict(r) for r in core.c.execute("SELECT v.*,e.sequence,'request' AS source FROM intent_interpretations v JOIN events e ON e.project_id=v.project_id AND e.id=v.event_id WHERE v.project_id=? AND v.input_id=?",(core.project,input_id)))
    if versions:
        latest=max(r['sequence'] for r in versions);heads=[r for r in versions if r['sequence']==latest]
        if len({r['digest'] for r in heads})!=1:
            require(for_write,'CONFLICT','Conflicting interpretations at the same event; submit a reconciled interpretation')
            return {'revision':max(r['revision'] for r in heads)}
        r=max(heads,key=lambda r:r['revision'])
        semantic={'input_id':input_id,'revision':r['revision'],'digest':r['digest'],'body':json.loads(r['body_json']),'source':r['source'],'event_id':r['event_id']}
    if has_table(core,'response_bindings'):
        r=core.c.execute('SELECT p.*,b.event_id AS binding_event,e.sequence AS binding_sequence FROM response_bindings b JOIN action_proposals p ON p.project_id=b.project_id AND p.id=b.proposal_id AND p.revision=b.proposal_revision JOIN events e ON e.project_id=b.project_id AND e.id=b.event_id WHERE b.project_id=? AND b.input_id=?',(core.project,input_id)).fetchone()
        if r and r['binding_sequence']>latest:
            require(r['revision']==core.c.execute('SELECT max(revision) FROM action_proposals WHERE project_id=? AND id=?',(core.project,r['id'])).fetchone()[0],'STALE','Approved proposal changed')
            p=json.loads(r['body_json']);envelope=json.loads(core.c.execute('SELECT body_json FROM input_envelopes WHERE project_id=? AND input_id=?',(core.project,input_id)).fetchone()[0])
            body=dict(acts=[p['action']],constraints=p['constraints'],targets=[p['target']],unresolved=[],evidence_spans=[{k:x[k] for k in ('part_id','start','end')} for x in envelope['parts'] if x['role']=='user_instruction'])
            return {'input_id':input_id,'revision':r['revision'],'digest':digest(body),'body':body,'source':'proposal_reply','event_id':r['binding_event'],'proposal':{'id':r['id'],'revision':r['revision'],'scope_digest':p['scope_digest']}}
    return semantic


def write(core,input_id,body,expected_revision,*,request_id=None):
    current=resolve(core,input_id,for_write=True);head=current['revision'] if current else 0
    require(type(expected_revision) is int and expected_revision==head,'STALE','Interpretation changed')
    if has_table(core,'input_intent_versions'):
        highest=core.c.execute('SELECT COALESCE(max(revision),0) FROM input_intent_versions WHERE project_id=? AND input_id=?',(core.project,input_id)).fetchone()[0]
        revision=max(head,highest)+1
        records.insert(core.c,'input_intent_versions',dict(project_id=core.project,input_id=input_id,revision=revision,body_json=encoded(body),digest=digest(body),event_id=core.event))
    else:
        # Compatibility for read/upgrade fixtures of the pre-input-authoring schema.
        require(request_id is not None,'UNSUPPORTED_SCHEMA','Input authoring requires the current schema')
        revision=head+1
        records.insert(core.c,'intent_interpretations',dict(project_id=core.project,request_id=request_id,revision=revision,input_id=input_id,body_json=encoded(body),digest=digest(body),event_id=core.event))
    return {'revision':revision,'digest':digest(body),'authority':'interpretation_only'}


def request(core,request_id):
    r=core.one('requests',request_id)
    return resolve(core,r['interaction_id'])


def matches(core,work,resolution):
    body=resolution['body'];targets=body['targets']
    if not targets:
        return core.c.execute('SELECT 1 FROM requests r JOIN request_goals g ON g.project_id=r.project_id AND g.request_id=r.id WHERE r.project_id=? AND r.interaction_id=? AND g.goal_id=?',(core.project,resolution['input_id'],work['goal_id'])).fetchone() is not None
    refs={('work_item',work['id'],work['revision']),('goal',work['goal_id'],records.get(core.c,core.project,'goal',work['goal_id'])['revision'])}
    seen=set()
    def visit(r):
        key=(r['kind'],r['id'],r['revision'])
        if key in seen:return
        seen.add(key);require(len(seen)<=128,'INVALID_INPUT','Selected work graph too large')
        for group,kind,idkey,revkey in [('plan_items','plan','plan_id','plan_revision'),('requirements','requirement','requirement_id','requirement_revision'),('decisions','decision','decision_id','decision_revision')]:
            for link in r['children'].get(group,[]):
                ref=(kind,link[idkey],link[revkey]);refs.add(ref)
                visit(records.get(core.c,core.project,*ref))
    visit(work)
    return any((t['kind'],t['id'],t['revision']) in refs for t in targets)


def validate(core,work,resolution):
    from .entry_runtime import validate_body
    row=core.c.execute('SELECT body_json FROM input_envelopes WHERE project_id=? AND input_id=?',(core.project,resolution['input_id'])).fetchone()
    require(row is not None,'PROVENANCE_UNAVAILABLE','Execution input unavailable')
    body=resolution['body'];validate_body(core,body,json.loads(row[0]))
    require(not body['unresolved'] and not set(body['acts'])&{'cancel','unresolved','answer'},'USER_ACTION_REQUIRED','Latest interpretation does not permit execution')
    revoked=core.c.execute('SELECT 1 FROM authorizations a JOIN executions x ON x.project_id=a.project_id AND x.authorization_id=a.id JOIN authorization_revocations z ON z.project_id=a.project_id AND z.authorization_id=a.id WHERE a.project_id=? AND a.interaction_id=? AND x.work_item_id=? AND x.work_revision=?',(core.project,resolution['input_id'],work['id'],work['revision'])).fetchone()
    require(not revoked,'USER_ACTION_REQUIRED','Referenced execution authorization was revoked')
    op=work['fields']['operation']
    require(op not in body['constraints'] and not (op=='design' and 'design_change' in body['constraints']),'USER_ACTION_REQUIRED','Current instruction prohibits this action')
    require(matches(core,work,resolution),'USER_ACTION_REQUIRED' if body['targets'] else 'INTERPRETATION_REQUIRED','Selected records do not include or support this work')


def authorize(core,work,resolution,*,thread=None,seen=None):
    validate(core,work,resolution)
    body=resolution['body'];op=work['fields']['operation'];acts=set(body['acts'])
    allowed=acts|({'validate'} if 'implement' in acts else set())
    if op=='investigate' and acts&{'implement','design','tasks','requirements','validate','deploy'}:allowed.add('investigate')
    if op in allowed:return {'current':resolution,'anchors':[]}
    require('resume' in acts,'USER_ACTION_REQUIRED','Saved interpretation does not request this action')
    seen=set() if seen is None else seen
    require(resolution['input_id'] not in seen and len(seen)<32,'CONFLICT','Continuation chain needs explicit reconciliation')
    seen.add(resolution['input_id'])
    current=core.c.execute('SELECT rowid AS ordinal,* FROM interactions WHERE project_id=? AND id=?',(core.project,resolution['input_id'])).fetchone()
    # Search saved requests/inputs as well as executions: first execution may be waiting for a choice.
    rows=core.c.execute('SELECT i.rowid AS ordinal,i.*,v.verifier FROM interactions i JOIN verified_interactions v ON v.project_id=i.project_id AND v.interaction_id=i.id JOIN input_envelopes e ON e.project_id=i.project_id AND e.input_id=i.id WHERE i.project_id=? AND i.rowid<? ORDER BY i.rowid DESC LIMIT 101',(core.project,current['ordinal'])).fetchall()
    for row in rows[:100]:
        expected=digest('codex-input-'+digest([thread,row['external_event_key']])) if thread else current['origin_context_digest']
        if row['origin_context_digest']!=expected:continue
        prior=resolve(core,row['id'])
        if prior is None or not matches(core,work,prior):continue
        # An applicable newer stop/prohibition wins; never skip it to find an older approval.
        receipt=authorize(core,work,prior,thread=thread,seen=seen)
        return {'current':resolution,'anchors':[receipt['current'],*receipt['anchors']]}
    require(len(rows)<=100,'STALE','Continuation history incomplete; bind an explicit action')
    raise CoreError('INTERPRETATION_REQUIRED','Connect this continuation to a permitted request for the selected work')
