"""Common learning API and execution preflight; no host hooks."""
from . import learning,failures,guidance,assurance
from .errors import require
from .execution import current_selection

OPS={
 'learning.propose':({'kind','expected_revision','body'},{'id','goal_id','links','evidence','snapshot_id'},False),
 'learning.accept':({'kind','id','revision','selection_id'},set(),True),
 'failure.report':({'evidence_id','classification'},{'case_id','expected','conditions'},False),
 'failure.attempt.record':({'case_id','evidence_id','action'},set(),False),
 'guideline.assess':({'guideline_id','revision','goal_id','snapshot_id','evidence_id','applicability','outcome','rationale'},{'work_id'},False),
 'verification.run.start':({'scenario_id','revision','snapshot_id','environment_evidence_id','environment'},{'execution_id'},False),
 'verification.run.finish':({'run_id','evidence_id','injection','behavior','recovery','trace'},set(),False),
 'assurance.exception':({'obligation_id','revision','snapshot_id','selection_id','rationale'},set(),True),
 'assurance.link_check':({'obligation_id','revision','work_id','work_revision','check_id'},set(),False),
 'assurance.evaluate':({'claim_id','snapshot_id'},set(),False),
}
HANDLERS={'learning.propose':learning.propose,'learning.accept':learning.accept,'failure.report':failures.report,'failure.attempt.record':failures.attempt,'guideline.assess':guidance.assess,'verification.run.start':assurance.start,'verification.run.finish':assurance.finish,'assurance.exception':assurance.exception,'assurance.link_check':assurance.link_check,'assurance.evaluate':assurance.record_evaluation}

def accepted(core,row):
    a=core.c.execute('SELECT revision,selection_id,contract_digest FROM learning_acceptances WHERE project_id=? AND kind=? AND id=? ORDER BY revision DESC LIMIT 1',(core.project,row['kind'],row['id'])).fetchone()
    if a:
        require(a['revision']==row['revision'],'STALE','Accepted learning contract changed')
        current_selection(core,a['selection_id'])
        require(a['contract_digest']==learning.contract_digest(core,row),'STALE','Accepted verification boundary changed')
    return bool(a)

def preflight(core,b,snapshot_id):
    operation=b['work']['fields']['operation']
    if operation not in ('implement','deploy'):return {'enforced':False}
    pack=guidance.projection(core,b['goal']['id'],snapshot_id,b['work']['id'])
    require(pack['complete'],'INCOMPLETE_CONTEXT','Guideline lookup incomplete')
    for row in pack['items']:
        if not accepted(core,row) or row['retired']:continue
        a=row['assessment']
        require(a and a['freshness']=='current' and a['applicability']!='unknown','GUIDANCE_REVIEW_REQUIRED','Review the relevant failure guideline')
        if a['applicability']=='applies':
            # Concrete obligations must link the guideline; prose alone is not verification.
            links=core.c.execute("SELECT 1 FROM learning_links l JOIN learning_records h ON h.project_id=l.project_id AND h.kind=l.owner_kind AND h.id=l.owner_id AND h.current_revision=l.owner_revision JOIN obligation_work_checks w ON w.project_id=l.project_id AND w.obligation_id=l.owner_id AND w.obligation_revision=l.owner_revision WHERE l.project_id=? AND l.owner_kind='obligation' AND l.role='guideline' AND l.target_id=? AND l.target_revision=? AND w.work_id=? AND w.work_revision=? LIMIT 1",(core.project,row['id'],row['revision'],b['work']['id'],b['work']['revision'])).fetchone()
            require(links is not None,'GUIDANCE_REVIEW_REQUIRED','Applied guideline needs a verification obligation')
    claims=learning.listing(core,'claim',b['goal']['id'],1001);require(len(claims)<=1000,'INCOMPLETE_CONTEXT','Claim lookup incomplete')
    result=[]
    for claim in claims:
        if claim['goal_id']!=b['goal']['id'] or not accepted(core,claim):continue
        phase='before_deploy' if operation=='deploy' else 'before_implementation'
        evaluation=assurance.evaluate(core,claim['id'],snapshot_id,phase)
        for obligation in assurance.obligations(core,claim):
            # Modifying an already accepted obligation requires renewed acceptance.
            accepted(core,obligation)
        require(all(i['result']=='PASS' or i.get('exception') for i in evaluation['items'] if i['required']),'ASSURANCE_INCOMPLETE','Required preflight verification is missing or failed')
        result.append(evaluation)
    return {'guidance_digest':pack['digest'],'assurance':result}
