"""Bind saved semantic intent to a verified current Codex input, not keywords."""
from skip_core.common import digest
from skip_core.errors import require
from skip_core.input_contract import normalize


def interpretation(core, principal):
    row=core.c.execute('SELECT e.input_id,e.digest,e.body_json FROM input_envelopes e JOIN interactions i ON i.project_id=e.project_id AND i.id=e.input_id JOIN verified_interactions v ON v.project_id=i.project_id AND v.interaction_id=i.id WHERE e.project_id=? AND i.external_event_key=? AND i.origin_context_digest=? AND v.verifier=?',
        (principal.project_id,principal.event_key,digest(principal.origin),principal.verifier)).fetchone()
    require(row is not None,'INTERPRETATION_REQUIRED','Capture this exact user input, then submit its meaning with skip_enter before beginning work')
    require(row['digest']==normalize(principal.user_text,principal.project_id)['digest'],'STALE','Current input differs from the saved interpretation')
    core.project=principal.project_id
    from skip_core.request_intent import resolve
    value=resolve(core,row['input_id'])
    require(value is not None,'INTERPRETATION_REQUIRED','Submit the meaning of this exact input with skip_enter; do not ask for different user wording')
    return value,None


def authorize(core,principal,thread,work,body,linked):
    from skip_core.request_intent import authorize as check
    return check(core,work,body,thread=thread)
