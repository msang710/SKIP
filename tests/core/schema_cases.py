from pathlib import Path
import sqlite3,json
ROOT=Path(__file__).resolve().parents[2]
schema='\n'.join(p.read_text() for p in sorted((ROOT/'skip_core/migrations').glob('*.sql')))
c=sqlite3.connect(':memory:',isolation_level=None);c.executescript(schema)
for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'"):
 c.execute('EXPLAIN INSERT INTO '+name+' DEFAULT VALUES').fetchall()
T='2026-09-10T00:00:00.000Z'; H='a'*64
checks=[]
def ins(t,**d):
 c.execute('INSERT INTO '+t+'('+','.join(d)+') VALUES('+','.join('?' for _ in d)+')',list(d.values()))
def seal(t,ident,rev=None):
 if rev is None:c.execute(f'UPDATE {t} SET sealed_at=? WHERE project_id=? AND id=?',(T,'p',ident))
 else:c.execute(f'UPDATE {t} SET sealed_at=?,content_digest=? WHERE project_id=? AND id=? AND revision=?',(T,H,'p',ident,rev))
def reject(label,fn):
 c.execute('SAVEPOINT rejected')
 try:
  fn()
 except sqlite3.IntegrityError:
  checks.append(label)
 else:raise AssertionError('Accepted invalid state: '+label)
 finally:c.execute('ROLLBACK TO rejected');c.execute('RELEASE rejected')
def event(e,n):ins('events',project_id='p',id=e,sequence=n,interaction_id='human',command_key=e,command_digest=H,kind='fixture',payload_json='{}',created_at=T)
for p in ['p','other']:
 ins('projects',id=p,name=p,state='active',created_at=T)
 ins('sources',project_id=p,id='s',name='main',kind='git',logical_path='.',created_at=T)
 ins('interactions',project_id=p,id='human',origin_context_digest=H,external_event_key='event',actor_kind='human',body='implement',body_digest=H,created_at=T)
 ins('verified_interactions',project_id=p,interaction_id='human',method='native_user_action',verifier='fixture-only-not-real-authority',proof_digest=H,verified_at=T)
 ins('requests',project_id=p,id='r',interaction_id='human',operation='implement',intent='keep reserved stock during shipping',intent_digest=H,created_at=T)
event('e1',1)
ins('interactions',project_id='p',id='agent',origin_context_digest=H,external_event_key='agent-event',actor_kind='agent',body='approved=true',body_digest=H,created_at=T)
reject('agent interaction cannot enter verified-human table',lambda:ins('verified_interactions',project_id='p',interaction_id='agent',method='host_user_turn',verifier='fixture',proof_digest=H,verified_at=T))
def head(kind,ident):
 d=dict(project_id='p',id=ident,origin_request_id='r',lifecycle='active',last_event_id='e1',created_at=T)
 if kind!='goal':d['goal_id']='g'
 ins(kind+'s',**d)
def version(kind,ident,rev,**fields):ins(kind+'_versions',project_id='p',id=ident,revision=rev,created_event_id='e1',created_at=T,**fields)
head('goal','g');version('goal','g',1,title='shipping',intent='keep stock reserved',success_definition='no duplicate assignment');seal('goal_versions','g',1)
head('decision','d');version('decision','d',1,question='Release stock?',rationale='Avoid reassignment',risk_summary='Duplicate allocation')
for pos,opt in enumerate(['keep','release']):ins('decision_options',project_id='p',decision_id='d',decision_revision=1,option_id=opt,label=opt,description=opt,consequences='business consequence',recommended=int(pos==0),position=pos)
seal('decision_versions','d',1)
reject('sealed decision text cannot change',lambda:c.execute("UPDATE decision_versions SET rationale='changed' WHERE project_id='p' AND id='d' AND revision=1"))
reject('sealed options cannot be appended',lambda:ins('decision_options',project_id='p',decision_id='d',decision_revision=1,option_id='third',label='third',description='',consequences='',recommended=0,position=2))
ins('selections',project_id='p',id='sel',decision_id='d',decision_revision=1,option_id='keep',interaction_id='human',event_id='e1',created_at=T)
reject('selection cannot reference nonexistent version option',lambda:ins('selections',project_id='p',id='wrong',decision_id='d',decision_revision=1,option_id='missing',interaction_id='human',event_id='e1',created_at=T))
head('requirement','req');version('requirement','req',1,title='reserved stock',statement='shipping stock remains reserved',rationale='implement chosen product rule')
ins('acceptance_criteria',project_id='p',requirement_id='req',requirement_revision=1,criterion_id='c1',description='concurrency',given_text='shipping active',when_text='release requested twice',then_text='reservation retained',required=1)
ins('requirement_decisions',project_id='p',requirement_id='req',requirement_revision=1,decision_id='d',decision_revision=1,rationale='keep selection')
ins('requirement_selections',project_id='p',requirement_id='req',requirement_revision=1,selection_id='sel',rationale='exact keep selection')
seal('requirement_versions','req',1)
head('plan','plan');version('plan','plan',1,title='locked validation',design_body='Revalidate within lock',scope_description='reservation service',alternatives_body='pre-lock check races',rollback_body='restore prior tested version')
ins('plan_items',project_id='p',plan_id='plan',plan_revision=1,item_id='pi1',title='locked revalidation',design_body='Acquire lease then recheck state',verification_body='concurrency integration test',position=0)
ins('plan_requirements',project_id='p',plan_id='plan',plan_revision=1,requirement_id='req',requirement_revision=1,rationale='enforces reservation rule')
seal('plan_versions','plan',1)
head('work_item','w');version('work_item','w',1,operation='implement',title='add guard',instruction_body='move state check inside lock',completion_definition='criterion c1 passes',workflow_depth='full',request_id='r')
ins('work_checks',project_id='p',work_item_id='w',work_revision=1,check_id='wc1',description='concurrency check',surface='integration',required=1)
reject('full work cannot seal without typed plan and requirement links',lambda:seal('work_item_versions','w',1))
ins('work_item_plan_items',project_id='p',work_item_id='w',work_revision=1,plan_id='plan',plan_revision=1,plan_item_id='pi1',rationale='implement this design')
ins('work_item_requirements',project_id='p',work_item_id='w',work_item_revision=1,requirement_id='req',requirement_revision=1,rationale='verify c1')
seal('work_item_versions','w',1)
reject('sealed work-plan link cannot change',lambda:c.execute("DELETE FROM work_item_plan_items WHERE project_id='p'"))
reject('cross-project decision reference rejected',lambda:ins('selections',project_id='other',id='sel',decision_id='d',decision_revision=1,option_id='keep',interaction_id='human',event_id='e1',created_at=T))
# Goal-less observations support minimum initial NOW without creating a goal.
ins('scopes',project_id='p',id='boot',goal_id=None,summary='observed files only',digest=H,created_at=T)
seal('scopes','boot')
ins('snapshots',project_id='p',id='boot-snap',scope_id='boot',digest=H,created_at=T);seal('snapshots','boot-snap')
checks.append('goal-less scope and snapshot support bootstrap observations')
ins('scopes',project_id='p',id='scope',goal_id='g',summary='reservation guard',digest=H,created_at=T)
ins('scope_paths',project_id='p',scope_id='scope',source_id='s',relative_path='allocation.py',access='modify');seal('scopes','scope')
ins('snapshots',project_id='p',id='snap',scope_id='scope',digest=H,created_at=T)
ins('snapshot_entries',project_id='p',snapshot_id='snap',source_id='s',relative_path='allocation.py',file_state='present',source_revision='test-revision',content_digest=H);seal('snapshots','snap')
for kind in ['goal','change']:
 ins('risk_assessments',project_id='p',id=kind,goal_id='g',goal_revision=1,scope_id='scope',snapshot_id='snap',kind=kind,policy_version='v1',level='high',rationale='inventory',assessor_interaction_id='agent',digest=H,created_at=T)
 for dim in ['business_rules','inventory','money','permissions','sensitive_data','persisted_data','external_state','boot_recovery']:ins('risk_factors',project_id='p',assessment_id=kind,dimension=dim,impact='unknown',explanation='fixture, not authorization proof')
 seal('risk_assessments',kind)
ins('authorizations',project_id='p',id='auth',request_id='r',interaction_id='human',action='implement',scope_id='scope',snapshot_id='snap',goal_risk_id='goal',change_risk_id='change',basis_digest=H,event_id='e1',created_at=T)
ins('authorization_selections',project_id='p',authorization_id='auth',selection_id='sel')
ins('authorization_work_items',project_id='p',authorization_id='auth',work_item_id='w',work_revision=1)
seal('authorizations','auth')
ins('executions',project_id='p',id='x',request_id='r',authorization_id='auth',work_item_id='w',work_revision=1,dispatch_context_digest=H,state='prepared',attempt_no=1,state_version=1,last_event_id='e1',created_at=T)
ins('deliveries',project_id='p',id='del',execution_id='x',message_key='message-1',payload='run w/1',payload_digest=H,state='pending',state_version=1,last_event_id='e1',created_at=T)
reject('duplicate delivery cannot create second execution send',lambda:ins('deliveries',project_id='p',id='del2',execution_id='x',message_key='message-2',payload='run w/1',payload_digest=H,state='pending',state_version=1,last_event_id='e1',created_at=T))
reject('state update requires CAS event',lambda:c.execute("UPDATE deliveries SET state='accepted' WHERE project_id='p' AND id='del'"))
ins('evidence',project_id='p',id='ev',snapshot_id='snap',execution_id='x',reporter_interaction_id='agent',surface='integration',result='PASS',provenance='agent_report',summary='concurrency passed',method='integration test',observed_at=T,event_id='e1',created_at=T)
ins('criterion_results',project_id='p',evidence_id='ev',requirement_id='req',requirement_revision=1,criterion_id='c1',verdict='PASS',explanation='reservation retained')
ins('work_check_results',project_id='p',evidence_id='ev',work_item_id='w',work_revision=1,check_id='wc1',verdict='PASS',explanation='observed output')
seal('evidence','ev')
reject('evidence cannot change after seal',lambda:c.execute("UPDATE evidence SET result='FAIL' WHERE project_id='p' AND id='ev'"))
ins('current_facts',project_id='p',id='fact',goal_id='g',statement='reservation guard implemented',source_id='s',snapshot_id='snap',evidence_id='ev',event_id='e1',created_at=T)
assert c.execute('SELECT count(*) FROM now_facts').fetchone()[0]==1
ins('fact_retractions',project_id='p',fact_id='fact',event_id='e1',reason='source changed',created_at=T)
assert c.execute('SELECT count(*) FROM now_facts').fetchone()[0]==0
checks.append('NOW projection excludes explicitly retracted facts')
# Exact joins prove traceability without text matching.
row=c.execute('''SELECT d.question,p.design_body,w.instruction_body,r.verdict FROM work_item_versions w
JOIN work_item_plan_items wp ON wp.project_id=w.project_id AND wp.work_item_id=w.id AND wp.work_revision=w.revision
JOIN plan_versions p ON p.project_id=wp.project_id AND p.id=wp.plan_id AND p.revision=wp.plan_revision
JOIN plan_requirements pr ON pr.project_id=p.project_id AND pr.plan_id=p.id AND pr.plan_revision=p.revision
JOIN requirement_decisions rd ON rd.project_id=pr.project_id AND rd.requirement_id=pr.requirement_id AND rd.requirement_revision=pr.requirement_revision
JOIN decision_versions d ON d.project_id=rd.project_id AND d.id=rd.decision_id AND d.revision=rd.decision_revision
JOIN criterion_results r ON r.project_id=pr.project_id AND r.requirement_id=pr.requirement_id AND r.requirement_revision=pr.requirement_revision
WHERE w.project_id='p' AND w.id='w' AND w.revision=1''').fetchone()
assert row==('Release stock?','Revalidate within lock','move state check inside lock','PASS')
checks.append('decision-plan-work-criterion evidence joins exact versions')
# New revision never rewrites historical references.
version('decision','d',2,question='New rule?',rationale='changed business rule',risk_summary='review needed')
for pos,opt in enumerate(['keep','release']):ins('decision_options',project_id='p',decision_id='d',decision_revision=2,option_id=opt,label=opt,description=opt,consequences='',recommended=0,position=pos)
seal('decision_versions','d',2);event('e2',2)
c.execute("UPDATE decisions SET current_revision=2,state_version=2,last_event_id='e2' WHERE project_id='p' AND id='d'")
assert c.execute('SELECT decision_revision FROM requirement_decisions').fetchone()[0]==1
checks.append('new decision revision preserves original requirement basis')
reject('head cannot target missing revision',lambda:c.execute("UPDATE decisions SET current_revision=99,state_version=3,last_event_id='e1' WHERE project_id='p' AND id='d'"))
head('work_item','small')
version('work_item','small',1,operation='implement',title='small edit',instruction_body='adjust label',completion_definition='label matches request',workflow_depth='compact',request_id='r')
ins('work_checks',project_id='p',work_item_id='small',work_revision=1,check_id='smoke',description='label observation',surface='ui',required=1)
seal('work_item_versions','small',1)
checks.append('compact work seals without artificial requirements or plans')
reject('sealed scope paths cannot be added',lambda:ins('scope_paths',project_id='p',scope_id='scope',source_id='s',relative_path='other.py',access='modify'))
reject('sealed evidence criterion result cannot change',lambda:c.execute("UPDATE criterion_results SET verdict='FAIL' WHERE project_id='p' AND evidence_id='ev'"))
reject('execution target cannot change',lambda:c.execute("UPDATE executions SET work_item_id='small',state_version=2,last_event_id='e2' WHERE project_id='p' AND id='x'"))
ins('risk_assessments',project_id='p',id='incomplete',goal_id='g',goal_revision=1,scope_id='scope',snapshot_id='snap',kind='change',policy_version='v1',level='unknown',rationale='missing dimensions',assessor_interaction_id='agent',digest=H,created_at=T)
reject('risk cannot seal with omitted dimensions',lambda:seal('risk_assessments','incomplete'))
reject('same work cannot execute concurrently in another environment',lambda:ins('executions',project_id='p',id='x-other',request_id='r',authorization_id='auth',work_item_id='w',work_revision=1,dispatch_context_digest='b'*64,state='prepared',attempt_no=2,state_version=1,last_event_id='e2',created_at=T))
event('e3',3)
c.execute("UPDATE executions SET state='finished',state_version=2,last_event_id='e3' WHERE project_id='p' AND id='x'")
ins('executions',project_id='p',id='x-next',request_id='r',authorization_id='auth',work_item_id='w',work_revision=1,dispatch_context_digest='b'*64,state='prepared',attempt_no=2,state_version=1,last_event_id='e3',created_at=T)
assert c.execute("SELECT count(*) FROM plans WHERE project_id='p'").fetchone()[0]==1
assert c.execute("SELECT count(*) FROM work_item_versions WHERE project_id='p' AND id='w'").fetchone()[0]==1
checks.append('same plan and work revision can be referenced by a later execution context without cloning; Core must obtain current user consent')
assert not c.execute("SELECT name FROM sqlite_master WHERE name IN ('host_bindings','agent_bindings')").fetchall()
checks.append('no persistent live host or agent binding tables')
assert not c.execute('PRAGMA foreign_key_check').fetchall()
assert c.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
checks.append('all foreign keys and integrity checks pass')
result={'status':'PASS','sqlite_version':sqlite3.sqlite_version,'table_count':c.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0],'checks':checks,'check_count':len(checks),'scope':'In-memory synthetic schema validation only; no production DB, host authority, or app integration.'}

print(json.dumps(result,ensure_ascii=False,indent=2))

c.close()
