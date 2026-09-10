"""Versioned user rules become context, never a model-supplied authority flag."""
import json
from .common import digest
DEFAULT_RULES = {
 'C-001':'Use the current conversation language; preserve technical names.',
 'C-002':'Reinvestigate evidence when the user corrects a fact.',
 'C-003':'Distinguish corrected facts, retained facts and pending evidence.',
 'C-004':'Split implementation at valid, testable states.',
 'C-005':'State containment and recovery for indivisible changes.',
 'C-006':'Keep source, test, runtime and visual evidence distinct.',
 'C-007':'Judge completion by the requested observable outcome.',
 'C-008':'Preserve NOT_RUN, partial verification and gaps.',
 'C-009':'Approval covers only the named action and scope.',
 'C-010':'Preserve unrelated user work and records.',
}

def effective(core, operation):
    records=core.current_settings();disabled=set();custom=[];unresolved=[]
    environment=core.context.identity[0] if core.context else None
    for record in records:
        body=json.loads(record['validated_body_json']);disabled.update(body['disabled_default_rule_ids'])
        for rule in body['custom_rules']:
            if rule['status']!='active':continue
            scope=rule['scope']
            if scope['kind']=='project':custom.append(rule)
            elif environment is None:unresolved.append(rule['id'])
            elif scope['environment_id']==environment and scope['operation']==operation:custom.append(rule)
    return {'defaults':{k:v for k,v in DEFAULT_RULES.items() if k not in disabled},'custom':custom,
            'unresolved_environment_rules':unresolved,'policy_digest':core.policy_digest()}
