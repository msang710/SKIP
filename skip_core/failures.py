"""Observed failures are preserved independently of later successful evidence."""
from . import records, learning
from .common import uid,now,text
from .errors import require

def report(core,p):
    e=core.one('evidence',p['evidence_id'])
    existing=core.c.execute('SELECT id,case_id FROM failure_occurrences WHERE project_id=? AND evidence_id=?',(core.project,e['id'])).fetchone()
    if existing:return dict(existing)
    require(p['classification'] in ('product','tool','reported','injected','unclassified'),'INVALID_INPUT','Unknown failure classification')
    require(e['result'] in ('FAIL','INCONCLUSIVE') or p['classification']=='injected','INVALID_INPUT','A failure observation is required')
    scope=core.one('scopes',core.one('snapshots',e['snapshot_id'])['scope_id'])
    if p.get('case_id'):
        case=learning.get(core,'failure',p['case_id'])
        require(case['goal_id']==scope['goal_id'],'PROJECT_MISMATCH','Case belongs to a different goal')
    else:
        case=learning.propose(core,{'kind':'failure','expected_revision':0,'goal_id':scope['goal_id'],'body':{
            'title':e['summary'][:160],'expected':p.get('expected','未確認 / not yet recorded'),
            'actual':e['summary'],'conditions':p.get('conditions',e['method']),'impact':'Not yet assessed',
            'cause':'Unknown; no causal conclusion from a failed result alone','cause_state':'unknown','state':'investigating'}})
    ident=uid();records.insert(core.c,'failure_occurrences',dict(project_id=core.project,id=ident,case_id=case['id'],case_revision=case['revision'],evidence_id=e['id'],classification=p['classification'],event_id=core.event,created_at=now()))
    return {'id':ident,'case_id':case['id'],'evidence_id':e['id']}

def attempt(core,p):
    case=learning.get(core,'failure',p['case_id']);e=core.one('evidence',p['evidence_id'])
    scope=core.one('scopes',core.one('snapshots',e['snapshot_id'])['scope_id'])
    require(scope['goal_id']==case['goal_id'],'PROJECT_MISMATCH','Attempt evidence outside case goal')
    ident=uid();records.insert(core.c,'failure_attempts',dict(project_id=core.project,id=ident,case_id=case['id'],case_revision=case['revision'],evidence_id=e['id'],action_body=text(p['action']),event_id=core.event,created_at=now()))
    return {'id':ident}
