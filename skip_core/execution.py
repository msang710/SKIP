"""Gate evaluation and execution preparation; external calls happen after commit."""
import json
from . import records
from .authority import snapshot
from .common import digest, encoded, now, uid
from .errors import require

ACTIVE_SQL = "('prepared','accepted','running','cancel_requested','cancellation_unknown')"


def paths(core, scope):
    return [dict(r) for r in core.c.execute('SELECT source_id,relative_path,access FROM scope_paths WHERE project_id=? AND scope_id=? ORDER BY source_id,relative_path',
                                          (core.project,scope))]


def current_selection(core, ident):
    row=core.one('selections',ident)
    decision=records.get(core.c,core.project,'decision',row['decision_id'])
    require(decision['revision']==row['decision_revision'] and decision['lifecycle']=='active','STALE','Decision basis changed')
    require(not core.c.execute('SELECT 1 FROM selection_revocations WHERE project_id=? AND selection_id=?',(core.project,ident)).fetchone()
        and not core.c.execute('SELECT 1 FROM selections WHERE project_id=? AND supersedes_id=?',(core.project,ident)).fetchone(),
        'STALE','Product selection changed')
    return row


def basis(core, work_id, revision):
    """Walk explicit links, checking heads. No document text is parsed for authority."""
    work=records.get(core.c,core.project,'work_item',work_id,revision)
    require(work['current_revision']==revision and work['lifecycle']=='active','STALE','Work changed')
    goal=records.get(core.c,core.project,'goal',work['goal_id'])
    require(goal['lifecycle']=='active','STALE','Goal is held or archived')
    refs={}; selections={}
    def visit(kind,ident,rev):
        key=(kind,ident,rev)
        if key in refs: return
        require(len(refs)<128,'INVALID_INPUT','Dependency graph too large')
        r=records.get(core.c,core.project,kind,ident,rev)
        require(r['revision']==r['current_revision'] and r['lifecycle']=='active' and r['goal_id']==goal['id'],
                'STALE','Referenced design or requirement changed')
        if r.get('origin') and kind!='decision':
            require(not json.loads(r['origin']['unresolved_json']),'INVALID_INPUT','Imported record has unresolved references')
            child_key={'work_item':'checks','requirement':'criteria','plan':'items'}.get(kind)
            require(not child_key or bool(r['children'][child_key]),'INVALID_INPUT','Recorded verification criteria are missing')
            if kind=='work_item' and r['fields']['workflow_depth']=='full':
                require(r['children']['requirements'] and r['children']['plan_items'],'INVALID_INPUT','Recorded plan and requirement links are incomplete')
        refs[key]=r
        for selection in r['children'].get('selections',[]):
            s=current_selection(core,selection['selection_id']); selections[s['id']]=s
        for link in r['children'].get('decisions',[]):
            visit('decision',link['decision_id'],link['decision_revision'])
        for link in r['children'].get('requirements',[]):
            visit('requirement',link['requirement_id'],link['requirement_revision'])
        for link in r['children'].get('plan_items',[]):
            visit('plan',link['plan_id'],link['plan_revision'])
    visit('work_item',work_id,revision)
    # A pending product question cannot be hidden by omitting a relationship.
    from .record_views import settled
    for d in core.c.execute("SELECT id,current_revision FROM decisions WHERE project_id=? AND goal_id=? AND lifecycle='active'",(core.project,goal['id'])):
        if settled(records.get(core.c,core.project,'decision',d['id'])):continue
        s=core.c.execute('SELECT s.id FROM selections s WHERE s.project_id=? AND s.decision_id=? AND s.decision_revision=? '
            'AND NOT EXISTS(SELECT 1 FROM selections n WHERE n.project_id=s.project_id AND n.supersedes_id=s.id) '
            'AND NOT EXISTS(SELECT 1 FROM selection_revocations v WHERE v.project_id=s.project_id AND v.selection_id=s.id)',
            (core.project,d['id'],d['current_revision'])).fetchone()
        if work['fields']['operation'] not in ('investigate','requirements','design'):
            require(s is not None,'USER_ACTION_REQUIRED','A product decision is still needed')
        if s:
            selections[s['id']]=current_selection(core,s['id'])
    for key,r in list(refs.items()):
        if r['kind']=='decision' and not settled(r) and work['fields']['operation'] not in ('investigate','requirements','design'):
            require(any(s['decision_id']==r['id'] and s['decision_revision']==r['revision'] for s in selections.values()),
                    'USER_ACTION_REQUIRED','Referenced decision has no selection')
    if work['fields']['operation'] not in ('investigate','requirements','design'):
        for r in refs.values():
            if r['kind'] not in ('requirement','plan'): continue
            linked = {link['selection_id'] for link in r['children'].get('selections', [])}
            for decision in r['children'].get('decisions', []):
                if settled(records.get(core.c,core.project,'decision',decision['decision_id'],decision['decision_revision'])):continue
                require(any(s['id'] in linked and s['decision_id']==decision['decision_id'] and
                            s['decision_revision']==decision['decision_revision'] for s in selections.values()),
                        'STALE','Design must identify the exact selected product option')
    # Dependency checks use recorded verification, not agent process exit.
    for dep in work['children']['dependencies']:
        dependency=records.get(core.c,core.project,'work_item',dep['depends_on_id'],dep['depends_on_revision'])
        require(dependency['current_revision']==dependency['revision'],'STALE','Dependency changed')
        checks=dependency['children']['checks']
        for check in checks:
            if not check['required']: continue
            row=core.c.execute('SELECT e.snapshot_id,e.result,r.verdict FROM work_check_results r JOIN evidence e ON e.project_id=r.project_id AND e.id=r.evidence_id '
                'WHERE r.project_id=? AND r.work_item_id=? AND r.work_revision=? AND r.check_id=? AND e.sealed_at IS NOT NULL '
                'ORDER BY (SELECT sequence FROM events ev WHERE ev.project_id=e.project_id AND ev.id=e.event_id) DESC LIMIT 1',(core.project,dependency['id'],dependency['revision'],check['check_id'])).fetchone()
            require(row is not None and row['result']=='PASS' and row['verdict']=='PASS','EXECUTION_ACTIVE','Dependency verification is incomplete')
            verify_snapshot(core,row['snapshot_id'])
    return {'goal':goal,'work':work,'records':list(refs.values()),'selections':list(selections.values()),'policy_digest':core.policy_digest()}


def verify_snapshot(core, ident):
    saved=core.one('snapshots',ident)
    require(not core.c.execute("SELECT 1 FROM evidence e JOIN record_origins o ON o.project_id=e.project_id AND o.record_id=e.id AND o.kind='evidence' WHERE e.project_id=? AND e.snapshot_id=?",(core.project,ident)).fetchone(),'STALE','Historical observation is not a current source measurement')
    require(core.context is not None,'CONTEXT_EXPIRED','Current source required')
    current=snapshot(core.context,paths(core,saved['scope_id']))
    require(current['digest']==saved['digest'],'STALE','Source changed; reassess the current scope')
    return saved


def risk_basis(core,p,b):
    risks=[core.one('risk_assessments',p[k+'_risk_id']) for k in ('goal','change')]
    for kind,r in zip(('goal','change'),risks):
        require(r['kind']==kind and r['sealed_at'] and r['goal_id']==b['goal']['id'] and r['goal_revision']==b['goal']['revision']
            and r['policy_version']==core.policy_digest(),'STALE','Risk or policy basis changed')
    require(risks[0]['scope_id']==risks[1]['scope_id'] and risks[0]['snapshot_id']==risks[1]['snapshot_id'], 'STALE','Risk scopes differ')
    operation=b['work']['fields']['operation']
    if operation not in ('investigate','requirements','design'):
        require(all(r['level']!='unknown' for r in risks),'USER_ACTION_REQUIRED','Investigate unknown failure costs first')
        require(all(r['level']=='low' for r in risks) or b['work']['fields']['workflow_depth']=='full',
                'USER_ACTION_REQUIRED','Material failure cost requires full design')
    saved=verify_snapshot(core,risks[0]['snapshot_id'])
    return risks,saved


def scope_overlap(a,b):
    if a['source_id']!=b['source_id'] or a['access']==b['access']=='read': return False
    left,right=a['relative_path'],b['relative_path']
    return left=='.' or right=='.' or left==right or left.startswith(right+'/') or right.startswith(left+'/')


def prepare(core,p,*,current=False):
    require(core.context is not None,'CONTEXT_EXPIRED','Connect the current conversation')
    core.context.check(start=not current)
    require(not current or core.context.can_continue,'TARGET_UNAVAILABLE','Current native turn cannot be verified')
    require(core.principal.origin==core.context.context_id,'PROJECT_MISMATCH','User action belongs to another context')
    if p.get('selection'):
        core._decision_select(p['selection'])
    b=basis(core,p['work_id'],p['revision'])
    risks,saved=risk_basis(core,p,b)
    proposed_paths=paths(core,saved['scope_id'])
    active=core.c.execute(f'SELECT x.work_item_id,a.scope_id FROM executions x JOIN authorizations a ON a.project_id=x.project_id AND a.id=x.authorization_id '
                          f'WHERE x.project_id=? AND x.state IN {ACTIVE_SQL}',(core.project,)).fetchall()
    for other in active:
        require(other['work_item_id']!=p['work_id'],'EXECUTION_ACTIVE','This work already has an unresolved execution')
        require(not any(scope_overlap(a,z) for a in proposed_paths for z in paths(core,other['scope_id'])),
                'EXECUTION_ACTIVE','Another active work overlaps this source scope')
    op=b['work']['fields']['operation']
    request_op='plan' if op in ('requirements','design','tasks') else 'investigate' if op=='validate' else op
    request=core.new_request(core.principal.user_text,request_op)
    if not core.c.execute('SELECT 1 FROM request_goals WHERE project_id=? AND request_id=? AND goal_id=?',(core.project,request,b['goal']['id'])).fetchone():
        records.insert(core.c,'request_goals',dict(project_id=core.project,request_id=request,goal_id=b['goal']['id']))
    auth=uid(); authority_basis=digest({'basis':b,'snapshot':saved['digest'],'risks':[r['digest'] for r in risks]})
    records.insert(core.c,'authorizations',dict(project_id=core.project,id=auth,request_id=request,interaction_id=core.interaction,
        action=op,scope_id=saved['scope_id'],snapshot_id=saved['id'],goal_risk_id=risks[0]['id'],change_risk_id=risks[1]['id'],
        basis_digest=authority_basis,event_id=core.event,created_at=now()))
    for selection in b['selections']:
        records.insert(core.c,'authorization_selections',dict(project_id=core.project,authorization_id=auth,selection_id=selection['id']))
    for r in b['records']:
        kind=r['kind']
        if kind in ('requirement','plan','work_item'):
            col='work_revision' if kind=='work_item' else kind+'_revision'
            records.insert(core.c,'authorization_'+kind+'s',dict(project_id=core.project,authorization_id=auth,**{kind+'_id':r['id'],col:r['revision']}))
    core.c.execute('UPDATE authorizations SET sealed_at=? WHERE project_id=? AND id=?',(now(),core.project,auth))
    execution,delivery,message=uid(),uid(),uid()
    attempt=core.c.execute('SELECT COALESCE(max(attempt_no),0)+1 FROM executions WHERE project_id=? AND work_item_id=? AND work_revision=?',
                         (core.project,p['work_id'],p['revision'])).fetchone()[0]
    records.insert(core.c,'executions',dict(project_id=core.project,id=execution,request_id=request,authorization_id=auth,
        work_item_id=p['work_id'],work_revision=p['revision'],state='prepared',attempt_no=attempt,state_version=1,
        last_event_id=core.event,dispatch_context_digest=core.context.fingerprint,created_at=now()))
    payload={'schema':'skip-execution/v1','project_id':core.project,'execution_id':execution,'request_id':request,
             'action':op,'basis':b,'scope':proposed_paths,'source_digest':saved['digest'],'enforcement':'advisory'}
    records.insert(core.c,'deliveries',dict(project_id=core.project,id=delivery,execution_id=execution,message_key=message,
        payload=encoded(payload),payload_digest=digest(payload),state='pending',state_version=1,last_event_id=core.event,created_at=now()))
    if current:
        core.event=core.event_record('execution.current-turn')
        transition(core,'deliveries',core.one('deliveries',delivery),'accepted')
        transition(core,'executions',core.one('executions',execution),'running',started_at=now(),result_receipt_digest=digest({'source':'current-user-turn','interaction':core.interaction}))
    return {'execution_id':execution,'delivery_id':delivery,'state':'running' if current else 'prepared','delivery_state':'accepted' if current else 'pending','action':op,'authorization':'ALLOW','scope':proposed_paths}


def transition(core, table, row, state, **values):
    values.update(state=state,state_version=row['state_version']+1,last_event_id=core.event)
    result=core.c.execute(f'UPDATE {table} SET '+','.join(k+'=?' for k in values)+' WHERE project_id=? AND id=? AND state_version=?',
                         (*values.values(),core.project,row['id'],row['state_version']))
    require(result.rowcount==1,'CONFLICT','Execution changed concurrently')


def cancel(core,p):
    x=core.one('executions',p['execution_id'])
    require(x['state_version']==p['expected_state_version'],'STALE','Execution changed')
    d=dict(core.c.execute('SELECT * FROM deliveries WHERE project_id=? AND execution_id=?',(core.project,x['id'])).fetchone())
    if x['state'] in ('finished','failed','cancelled'): return {'execution_id':x['id'],'state':x['state']}
    if d['state']=='pending':
        transition(core,'deliveries',d,'cancelled')
        transition(core,'executions',x,'cancelled',finished_at=now())
        state='cancelled'
    else:
        transition(core,'executions',x,'cancel_requested')
        state='cancel_requested'
    return {'execution_id':x['id'],'state':state,'code_changes_reverted':False}
