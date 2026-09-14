"""Bind saved semantic intent to a verified current Codex input, not keywords."""
import json
from skip_core.common import digest
from skip_core.errors import require
from skip_core import records
from skip_core.entry_runtime import validate_body
from skip_core.input_contract import normalize


def interpretation(core, principal):
    row=core.c.execute('SELECT e.input_id,e.digest,e.body_json FROM input_envelopes e JOIN interactions i ON i.project_id=e.project_id AND i.id=e.input_id JOIN verified_interactions v ON v.project_id=i.project_id AND v.interaction_id=i.id WHERE e.project_id=? AND i.external_event_key=? AND i.origin_context_digest=? AND v.verifier=?',
        (principal.project_id,principal.event_key,digest(principal.origin),principal.verifier)).fetchone()
    require(row is not None,'INTERPRETATION_REQUIRED','Capture this exact user input, then submit its meaning with skip_enter before beginning work')
    envelope=json.loads(row['body_json'])
    require(row['digest']==normalize(principal.user_text,principal.project_id)['digest'],'STALE','Current input differs from the saved interpretation')
    linked=core.c.execute('SELECT request_id,goal_id FROM input_materializations WHERE project_id=? AND input_id=?',(principal.project_id,row['input_id'])).fetchone()
    version=core.c.execute('SELECT body_json FROM intent_interpretations WHERE project_id=? AND request_id=? ORDER BY revision DESC LIMIT 1',(principal.project_id,linked['request_id'])).fetchone() if linked else core.c.execute('SELECT body_json FROM input_intent_versions WHERE project_id=? AND input_id=? ORDER BY revision DESC LIMIT 1',(principal.project_id,row['input_id'])).fetchone()
    if version is None:
        # An already verified exact proposal reply is also saved semantic scope.
        reply=core.c.execute('SELECT p.body_json,p.id,p.revision FROM response_bindings b JOIN action_proposals p ON p.project_id=b.project_id AND p.id=b.proposal_id AND p.revision=b.proposal_revision WHERE b.project_id=? AND b.input_id=?',(principal.project_id,row['input_id'])).fetchone()
        if reply:
            head=core.c.execute('SELECT max(revision) FROM action_proposals WHERE project_id=? AND id=?',(principal.project_id,reply['id'])).fetchone()[0]
            require(head==reply['revision'],'STALE','Approved proposal changed')
            proposal=json.loads(reply['body_json'])
            body=dict(acts=[proposal['action']],constraints=proposal['constraints'],targets=[proposal['target']],unresolved=[],evidence_spans=[{k:p[k] for k in ('part_id','start','end')} for p in envelope['parts'] if p['role']=='user_instruction'])
            version={'body_json':json.dumps(body)}
    require(version is not None,'INTERPRETATION_REQUIRED','Submit the meaning of this exact input with skip_enter; do not ask for different user wording')
    body=json.loads(version['body_json']);core.project=principal.project_id
    validate_body(core,body,envelope)
    require(not body['unresolved'] and not set(body['acts'])&{'cancel','unresolved'},'USER_ACTION_REQUIRED','Current interpretation stops work or needs resolution')
    return body,dict(linked) if linked else None


def authorize(core,principal,thread,work,body,linked):
    op=work['fields']['operation'];acts=set(body['acts'])
    require(op not in body['constraints'] and not (op=='design' and 'design_change' in body['constraints']),'USER_ACTION_REQUIRED','Current instruction prohibits this action')
    if linked:require(linked['goal_id']==work['goal_id'],'PROJECT_MISMATCH','Current input selected another goal')
    targets=body['targets']
    require(linked or targets,'INTERPRETATION_REQUIRED','Bind the interpreted input to its goal or exact work before execution')
    for target in targets:
        r=records.get(core.c,principal.project_id,target['kind'],target['id'],target['revision'])
        require(r['goal_id']==work['goal_id'],'PROJECT_MISMATCH','Current input selected another goal')
        if target['kind']=='work_item':require(target['id']==work['id'] and target['revision']==work['revision'],'USER_ACTION_REQUIRED','Current input selected different work')
    allowed=acts|({'validate'} if 'implement' in acts else set())
    if op in allowed:return
    require('resume' in acts,'USER_ACTION_REQUIRED','Saved interpretation does not request this action')
    require({'kind':'work_item','id':work['id'],'revision':work['revision']} in targets,'INTERPRETATION_REQUIRED','A continuation must identify the exact work being resumed')
    # Continuation inherits only the action of a verified request in this thread.
    anchor=core.c.execute('SELECT i.*,r.operation FROM requests r JOIN interactions i ON i.project_id=r.project_id AND i.id=r.interaction_id JOIN verified_interactions v ON v.project_id=i.project_id AND v.interaction_id=i.id WHERE r.project_id=? AND r.id=? AND v.verifier=?',
        (principal.project_id,work['fields']['request_id'],principal.verifier)).fetchone()
    require(anchor is not None and anchor['origin_context_digest']==digest('codex-input-'+digest([thread,anchor['external_event_key']])),'USER_ACTION_REQUIRED','Continuation lacks an original request in this conversation')
    saved=core.c.execute('SELECT body_json FROM intent_interpretations WHERE project_id=? AND request_id=? ORDER BY revision DESC LIMIT 1',(principal.project_id,work['fields']['request_id'])).fetchone()
    require(saved is not None,'INTERPRETATION_REQUIRED','Interpret the original request before inheriting its action')
    original=json.loads(saved['body_json']);original_acts=set(original['acts'])
    require(not original['unresolved'] and not original_acts&{'cancel','unresolved'} and op not in original['constraints'],'USER_ACTION_REQUIRED','Original request does not permit continuation')
    require(op in original_acts or (op=='validate' and 'implement' in original_acts),'USER_ACTION_REQUIRED','Continuation cannot expand the original action')
