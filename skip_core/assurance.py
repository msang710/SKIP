"""Claims are supported only by matching required boundary evidence, never test counts."""
import json
from . import records,learning
from .common import uid,now,encoded,digest
from .errors import require,CoreError
from .execution import verify_snapshot,paths

RESULTS={'PASS','FAIL','NOT_RUN','INCONCLUSIVE'}
def link(row,role):
    values=[r for r in row['links'] if r['role']==role]
    require(len(values)==1,'INVALID_INPUT','Required relation missing')
    return values[0]

def environment_matches(required,actual):
    for key,spec in required.items():
        if key not in actual:return False
        v=actual[key];expected=spec['value'];op=spec['op']
        if op=='eq' and (type(v)!=type(expected) or v!=expected):return False
        if op=='in' and not any(type(v)==type(e) and v==e for e in expected):return False
        if op in ('gte','lte'):
            if type(v) not in (int,float):return False
            if op=='gte' and v<expected or op=='lte' and v>expected:return False
    return True

def start(core,p):
    scenario=learning.get(core,'scenario',p['scenario_id'],p['revision']);require(scenario['revision']==scenario['current_revision'],'STALE','Scenario changed')
    snap=verify_snapshot(core,p['snapshot_id']);env=core.one('evidence',p['environment_evidence_id'])
    require(env['snapshot_id']==snap['id'] and env['result']=='PASS','INVALID_INPUT','Observed environment evidence required')
    require(isinstance(p['environment'],dict) and len(p['environment'])<=64,'INVALID_INPUT','Bounded environment manifest required')
    payload=core.c.execute('SELECT content FROM evidence_payloads WHERE project_id=? AND evidence_id=?',(core.project,env['id'])).fetchone()
    require(payload is not None,'INVALID_INPUT','Environment evidence must contain its manifest')
    try:manifest=json.loads(payload['content'])
    except (ValueError,TypeError):manifest=None
    require(manifest==p['environment'],'INVALID_INPUT','Environment differs from evidence manifest')
    if scenario['goal_id']:require(core.one('scopes',snap['scope_id'])['goal_id']==scenario['goal_id'],'PROJECT_MISMATCH','Run outside scenario goal')
    execution=p.get('execution_id')
    if execution:
        x=core.one('executions',execution);require(x['state']=='running','CONFLICT','Execution is not running')
    ident=uid();records.insert(core.c,'verification_runs',dict(project_id=core.project,id=ident,scenario_id=scenario['id'],scenario_revision=scenario['revision'],snapshot_id=snap['id'],environment_evidence_id=env['id'],environment_json=encoded(p['environment']),execution_id=execution,started_event_id=core.event,created_at=now()))
    return {'id':ident,'state':'started','provenance':env['provenance']}

def finish(core,p):
    run=core.one('verification_runs',p['run_id']);e=core.one('evidence',p['evidence_id'])
    require(e['snapshot_id']==run['snapshot_id'],'INVALID_INPUT','Run evidence scope differs')
    for k in ('injection','behavior','recovery'):require(p[k] in RESULTS,'INVALID_INPUT','Unknown result')
    require(e['result']==p['behavior'],'INVALID_INPUT','Behavior verdict contradicts evidence')
    trace=p['trace'];require(isinstance(trace,dict) and set(trace)=={'attempts','injected','events'} and type(trace['attempts']) is int and type(trace['injected']) is int and 0<=trace['injected']<=trace['attempts'] and isinstance(trace['events'],list) and len(trace['events'])<=1000,'INVALID_INPUT','Invalid injection trace')
    scenario=learning.get(core,'scenario',run['scenario_id'],run['scenario_revision'])
    if scenario['body']['fault'] and p['injection']=='PASS':require(trace['injected']>0 and trace['events'],'INVALID_INPUT','Fault injection was not observed')
    if p['behavior']!='NOT_RUN':verify_snapshot(core,run['snapshot_id'])
    records.insert(core.c,'verification_results',dict(project_id=core.project,run_id=run['id'],injection=p['injection'],behavior=p['behavior'],recovery=p['recovery'],evidence_id=e['id'],trace_json=encoded(trace),event_id=core.event,created_at=now()))
    if p['behavior']=='FAIL':
        from .failures import report
        report(core,{'evidence_id':e['id'],'classification':'product'})
    return {'run_id':run['id'],'state':'finished','behavior':p['behavior']}

def obligations(core,claim):
    ids=core.c.execute("SELECT DISTINCT v.id FROM learning_versions v JOIN learning_records h ON h.project_id=v.project_id AND h.kind=v.kind AND h.id=v.id AND h.current_revision=v.revision JOIN learning_links l ON l.project_id=v.project_id AND l.owner_kind=v.kind AND l.owner_id=v.id AND l.owner_revision=v.revision WHERE v.project_id=? AND v.kind='obligation' AND l.role='claim' AND l.target_id=? AND l.target_revision=? ORDER BY v.id",(core.project,claim['id'],claim['revision']))
    return [learning.get(core,'obligation',r['id']) for r in ids]

def evaluate(core,claim_id,snapshot_id,phase=None):
    claim=learning.get(core,'claim',claim_id);snapshot=verify_snapshot(core,snapshot_id)
    if claim['goal_id']:require(core.one('scopes',snapshot['scope_id'])['goal_id']==claim['goal_id'],'PROJECT_MISMATCH','Evaluation scope outside claim')
    if claim['goal_id']:
        require(records.get(core.c,core.project,'goal',claim['goal_id'])['revision']==claim['goal_revision'],'STALE','Claim goal changed')
    declared={(p['source_id'],p['relative_path']) for p in paths(core,claim['scope_id'])}
    actual={(p['source_id'],p['relative_path']) for p in paths(core,snapshot['scope_id'])}
    require(declared==actual,'SCOPE_MISMATCH','Evidence does not cover the declared claim scope')
    items=[];obs=obligations(core,claim);basis=[claim['digest'],snapshot_id,core.policy_digest()]
    for obligation in obs:
        envref=link(obligation,'environment');profile=learning.get(core,'environment',envref['id'],envref['revision'])
        boundary=link(obligation,'boundary');b=learning.get(core,'boundary',boundary['id'],boundary['revision'])
        basis.extend([obligation['digest'],profile['digest'],profile['current_revision'],b['digest'],b['current_revision'],obligation['accepted']])
        scenarios=core.c.execute("SELECT v.id,v.revision FROM learning_versions v JOIN learning_records h ON h.project_id=v.project_id AND h.kind=v.kind AND h.id=v.id AND h.current_revision=v.revision JOIN learning_links l ON l.project_id=v.project_id AND l.owner_kind=v.kind AND l.owner_id=v.id AND l.owner_revision=v.revision WHERE v.project_id=? AND v.kind='scenario' AND l.role='obligation' AND l.target_id=? AND l.target_revision=? ORDER BY v.id",(core.project,obligation['id'],obligation['revision'])).fetchall()
        results=[];all_evidence=[]
        for sr in scenarios:
            scenario=learning.get(core,'scenario',sr['id'],sr['revision']);basis.append(scenario['digest'])
            runs=core.c.execute('SELECT r.*,v.behavior,v.injection,v.recovery,v.evidence_id FROM verification_runs r LEFT JOIN verification_results v ON v.project_id=r.project_id AND v.run_id=r.id WHERE r.project_id=? AND r.scenario_id=? AND r.scenario_revision=? ORDER BY r.id',(core.project,sr['id'],sr['revision'])).fetchall()
            verdicts=[]
            for run in runs:
                basis.append(dict(run))
                run_snapshot=core.one('snapshots',run['snapshot_id'])
                if run_snapshot['digest']!=snapshot['digest']:continue
                run_scope={(p['source_id'],p['relative_path']) for p in paths(core,run_snapshot['scope_id'])}
                if run_scope!=actual:continue
                if run['evidence_id']:
                    e=core.one('evidence',run['evidence_id'])
                    if e['surface']=='source' or ('surfaces' in obligation['body'] and e['surface'] not in obligation['body']['surfaces']):continue
                if not environment_matches(profile['body']['requirements'],json.loads(run['environment_json'])):continue
                if scenario['body']['fault'] and run['injection']!='PASS':continue
                if scenario['body']['kind']=='recovery' and run['recovery']!='PASS':verdicts.append('INCONCLUSIVE');continue
                verdicts.append(run['behavior'] or 'NOT_RUN')
                if run['evidence_id']:all_evidence.append(run['evidence_id'])
            results.append('conflict' if 'FAIL' in verdicts and 'PASS' in verdicts else 'FAIL' if 'FAIL' in verdicts else 'PASS' if verdicts and all(v=='PASS' for v in verdicts) else 'NOT_RUN')
        state='conflict' if 'conflict' in results else 'FAIL' if 'FAIL' in results else 'PASS' if results and all(v=='PASS' for v in results) else 'NOT_RUN'
        if profile['current_revision']!=profile['revision'] or b['current_revision']!=b['revision']:state='STALE'
        checks=core.c.execute('SELECT * FROM obligation_work_checks WHERE project_id=? AND obligation_id=? AND obligation_revision=?',(core.project,obligation['id'],obligation['revision'])).fetchall()
        for check in checks:
            w=records.get(core.c,core.project,'work_item',check['work_id'],check['work_revision'])
            if w['current_revision']!=check['work_revision']:state='STALE';continue
            matching=core.c.execute('SELECT evidence_id,verdict FROM work_check_results WHERE project_id=? AND work_item_id=? AND work_revision=? AND check_id=?',(core.project,check['work_id'],check['work_revision'],check['check_id'])).fetchall()
            if not any(r['evidence_id'] in all_evidence and r['verdict']=='PASS' for r in matching) and state=='PASS':state='NOT_RUN'
        basis.extend(dict(c) for c in checks)
        items.append({'id':obligation['id'],'revision':obligation['revision'],'title':obligation['body']['title'],'phase':obligation['body']['phase'],'required':obligation['body']['required'],'accepted':obligation['accepted'],'result':state,'evidence_ids':all_evidence})
    # Dependencies are requirements too; stale/missing versions cannot count as satisfied.
    byid={i['id']:i for i in items}
    visiting=set();resolved=set()
    definitions={o['id']:o for o in obs}
    def resolve(ident):
        if ident in resolved:return byid[ident]['result']
        if ident in visiting:return 'DEPENDENCY_PENDING'
        visiting.add(ident)
        item=byid[ident]
        pending=any(dep['id'] not in byid or byid[dep['id']]['revision']!=dep['revision'] or resolve(dep['id'])!='PASS'
                    for dep in definitions[ident]['links'] if dep['role']=='dependency')
        if pending and item['result'] not in ('FAIL','conflict','STALE'):
            item['result']='DEPENDENCY_PENDING'
        visiting.remove(ident);resolved.add(ident)
        return item['result']
    for ident in byid:resolve(ident)
    if phase:items=[i for i in items if i['phase']==phase]
    for item in items:
        exceptions=core.c.execute('SELECT * FROM assurance_exceptions WHERE project_id=? AND obligation_id=? AND obligation_revision=? AND snapshot_id=? ORDER BY created_at DESC',(core.project,item['id'],item['revision'],snapshot_id)).fetchall()
        item['exception']=None
        from .execution import current_selection
        for ex in exceptions:
            try:current_selection(core,ex['selection_id'])
            except CoreError:continue
            item['exception']={'id':ex['id'],'rationale':ex['rationale'],'selection_id':ex['selection_id']};break
        basis.append(item['exception'])
    required=[i for i in items if i['required']];passed=sum(i['result']=='PASS' for i in required)
    verdict='contradicted' if any(i['result']=='FAIL' for i in required) else 'supported' if required and passed==len(required) else 'undetermined'
    return {'claim_id':claim_id,'revision':claim['revision'],'accepted':claim['accepted'],'items':items,'coverage':'complete' if required and passed==len(required) else 'partial' if passed else 'none','verdict':verdict,'freshness':'current','basis_digest':digest(basis),'snapshot_id':snapshot_id,'notice':'Evidence supports only the declared conditions; not a guarantee of all future executions.'}

def record_evaluation(core,p):
    result=evaluate(core,p['claim_id'],p['snapshot_id']);ident=uid()
    records.insert(core.c,'assurance_evaluations',dict(project_id=core.project,id=ident,claim_id=result['claim_id'],claim_revision=result['revision'],snapshot_id=p['snapshot_id'],body_json=encoded(result),basis_digest=result['basis_digest'],event_id=core.event,created_at=now()))
    return {'id':ident,**result}


def exception(core,p):
    from .execution import current_selection
    from .common import text
    o=learning.get(core,'obligation',p['obligation_id'],p['revision'])
    require(o['revision']==o['current_revision'],'STALE','Obligation changed')
    selection=current_selection(core,p['selection_id']);d=records.get(core.c,core.project,'decision',selection['decision_id'])
    require(o['goal_id']==d['goal_id'],'PROJECT_MISMATCH','Exception outside goal')
    verify_snapshot(core,p['snapshot_id']);ident=uid()
    records.insert(core.c,'assurance_exceptions',dict(project_id=core.project,id=ident,obligation_id=o['id'],obligation_revision=o['revision'],snapshot_id=p['snapshot_id'],selection_id=selection['id'],rationale=text(p['rationale']),event_id=core.event,created_at=now()))
    return {'id':ident,'verdict':'exception_accepted','not_a_pass':True}


def link_check(core,p):
    o=learning.get(core,'obligation',p['obligation_id'],p['revision']);w=records.get(core.c,core.project,'work_item',p['work_id'],p['work_revision'])
    require(o['goal_id']==w['goal_id'] and o['revision']==o['current_revision'] and w['revision']==w['current_revision'],'STALE','Check link basis differs')
    require(any(c['check_id']==p['check_id'] for c in w['children']['checks']),'NOT_FOUND','Work check unavailable')
    records.insert(core.c,'obligation_work_checks',dict(project_id=core.project,obligation_id=o['id'],obligation_revision=o['revision'],work_id=w['id'],work_revision=w['revision'],check_id=p['check_id']))
    return {'obligation_id':o['id'],'work_id':w['id'],'check_id':p['check_id']}
