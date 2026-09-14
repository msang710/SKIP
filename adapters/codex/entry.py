"""Use the current Codex user turn. Never launch an unrelated app-server session."""
import argparse
from dataclasses import replace
import json
import os
import re
from pathlib import Path
from skip_core.authority import Principal,ExecutionContext
from skip_core.common import digest,encoded
from skip_core.db import Database,default_path
from skip_core.errors import CoreError,require
from skip_core.service import Core
from adapters.common.identity import resolve_project
from .provenance import current_user,proposal_reply
from skip_core.input_contract import normalize,classify


def run(workspace,session_root,thread_id,db_path,*,project_id=None,goal_id=None,activate=False,begin=None,finish=None,update_goals=None):
    require(sum(bool(x) for x in (activate,begin,finish,update_goals is not None))<=1,'INVALID_INPUT','Choose one native operation')
    workspace=workspace.resolve(strict=True)
    user=current_user(session_root,thread_id,workspace)
    project=project_id or resolve_project(workspace,str(workspace),db_path)
    latest_id=user['id']
    if finish:
        # Finishing reports an already-authorized execution; it starts no work.
        with Database(db_path) as existing:
            anchor=existing.connection.execute('SELECT i.* FROM executions x JOIN authorizations a ON a.project_id=x.project_id AND a.id=x.authorization_id JOIN interactions i ON i.project_id=a.project_id AND i.id=a.interaction_id JOIN verified_interactions v ON v.project_id=i.project_id AND v.interaction_id=i.id WHERE x.project_id=? AND x.id=? AND v.verifier=?',(project,finish,'codex-local-session-record')).fetchone()
            require(anchor is not None and anchor['origin_context_digest']==digest('codex-input-'+digest([thread_id,anchor['external_event_key']])),'USER_ACTION_REQUIRED','Execution belongs to another conversation')
            user={**user,'id':anchor['external_event_key'],'text':anchor['body']}
    identity=('codex',thread_id,user['id'])
    def verify():
        latest=current_user(session_root,thread_id,workspace)
        require(latest['id']==latest_id,'CONTEXT_EXPIRED','The current user turn changed')
        return identity
    origin='codex-input-'+digest([thread_id,user['id']])
    ctx=ExecutionContext(project,{'main':workspace},identity,verify,can_continue=True,context_id=origin,caller_verified=True)
    from adapters.common.caller import participant_identity
    ctx.participant=participant_identity(workspace)
    # Stable per selected host user turn; process restarts do not invent a new request.
    principal=Principal(project,origin,kind='human',method='host_user_turn',
                        verifier='codex-local-session-record',event_key=user['id'],user_text=user['text'])
    envelope=normalize(user['text'],project)
    interpretation=classify(envelope)
    acts=interpretation['acts']
    operation='implement' if 'implement' in acts else 'deploy' if 'deploy' in acts else 'plan' if set(acts)&{'design','requirements','tasks'} else 'investigate' if set(acts)&{'investigate','validate'} else 'answer'
    if activate:
        require(re.search(r'(?<!\w)[/$]skip\b|\bSKIP\b',user['text'],re.I),'USER_ACTION_REQUIRED','Activation requires an explicit SKIP request')
    with Database(db_path,create=activate) as db:
        core=Core(db)
        if activate:
            command={'schema':'skip-core/v1','command':'project.activate','project_id':project,'key':digest([user['id'],'activate']),
                     'payload':{'name':workspace.name}}
            result=core.execute(command,principal,ctx)
            result['data']['project_profile']=core.query('status',{},principal,ctx)['data']['project_profile']
            return result
        if update_goals is not None:
            require(not (activate or begin or finish),'INVALID_INPUT','Choose one native operation')
            return core.execute({'schema':'skip-core/v1','command':'goal.transition','project_id':project,
                'key':digest([user['id'],'goal.transition',update_goals]),'payload':update_goals},principal,ctx)
        if not begin and not finish and operation=='answer' and re.fullmatch(r'\s*(그래\s*)?(승인이야|승인해|승인|동의해|approve|approved)[.!\s]*',user['text'],re.I):
            candidates=[]
            if goal_id:
                rows=db.connection.execute('SELECT p.* FROM action_proposals p JOIN request_goals g ON g.project_id=p.project_id AND g.request_id=p.request_id WHERE p.project_id=? AND g.goal_id=? AND NOT EXISTS(SELECT 1 FROM action_proposals n WHERE n.project_id=p.project_id AND n.id=p.id AND n.revision>p.revision) LIMIT 101',(project,goal_id)).fetchall()
                require(len(rows)<=100,'AMBIGUOUS_INPUT','Proposal lookup incomplete')
                candidates=[dict(r) for r in rows]
            ref=proposal_reply(user,candidates)
            if ref:
                principal=replace(principal,response_ref=ref)
                result=core.execute({'schema':'skip-core/v1','command':'response.bind','project_id':project,'key':digest([user['id'],'response']),'payload':{'proposal_id':ref[0],'revision':ref[1]}},principal,ctx)
                proposal=next(c for c in candidates if c['id']==ref[0] and c['revision']==ref[1])
                proposed=json.loads(proposal['body_json'])
                acts=[proposed['action']]
                operation='plan' if proposed['action'] in ('design','requirements','tasks') else proposed['action']
                if not begin and not finish:
                    if goal_id:result['data']['context']=core.query('context',{'goal_id':goal_id,'stage':'restore'},principal,ctx)['data']
                    return result
        if begin or finish:
            if begin:
                from .execution_intent import interpretation as saved_interpretation, authorize
                body,linked=saved_interpretation(core,principal)
                work=core.query('record',{'kind':'work_item','id':begin['work_id'],'revision':begin['revision']},principal,ctx)['data']
                authorize(core,principal,thread_id,work,body,linked)
                semantic_digest=digest([body,linked])
                def verify_execution():
                    identity_now=verify()
                    current_body,current_link=saved_interpretation(core,principal)
                    require(digest([current_body,current_link])==semantic_digest,'STALE','Execution interpretation changed; refresh before continuing')
                    from skip_core import records
                    current_work=records.get(core.c,project,'work_item',begin['work_id'],begin['revision'])
                    authorize(core,principal,thread_id,current_work,current_body,current_link)
                    return identity_now
                ctx.verify=verify_execution
            op='execution.begin_current' if begin else 'execution.finish_current'
            payload=begin if begin else {'execution_id':finish}
            return core.execute({'schema':'skip-core/v1','command':op,'project_id':project,'key':digest([user['id'],op,payload]),'payload':payload},principal,ctx)
        if user['text'].startswith('SKIP 사용자 선택\n'):
            selected=json.loads(user['text'].split('\n',1)[1])
            require(set(selected)=={'schema','project_id','decision_id','revision','option_id'} and selected['schema']=='skip-user-selection/v1'
                    and selected['project_id']==project,'INVALID_INPUT','Invalid selected card')
            p={k:selected[k] for k in ('decision_id','revision','option_id')}
            return core.execute({'schema':'skip-core/v1','command':'decision.select','project_id':project,'key':digest(user['id']),'payload':p},principal,ctx)
        captured=core.execute({'schema':'skip-core/v1','command':'input.ingest','project_id':project,'key':digest([user['id'],'input']),'payload':{}},principal,ctx)
        entry=core.query('entry.inspect',{'input_id':captured['data']['input_id']},principal,ctx)['data']
        def with_context(result, selected_goal):
            result['data']['entry_basis']=entry
            if selected_goal:
                result['data']['context']=core.query('context',{'goal_id':selected_goal,'stage':'restore'},principal,ctx)['data']
            return result
        if envelope['targets']:
            target=envelope['targets'][0]
            selected=core.query('record',target,principal,ctx)['data']
            require(selected['current_revision']==target['revision'],'STALE','Selected record changed')
            require(not goal_id or selected['goal_id']==goal_id,'PROJECT_MISMATCH','Selected record outside goal')
            goal_id=selected['goal_id']
            if operation=='answer':return {'schema':'skip-core/v1','status':'ok','data':{'record':selected,'entry_basis':entry,'authority':'reading_material'},'enforcement':'advisory'}
        # Native entry captures the actual turn. The calling agent supplies its
        # semantic interpretation through entry.submit; no keyword creates a goal.
        result=core.query('status',{'goal_id':goal_id} if goal_id else {},principal,ctx)
        return with_context(result,goal_id)



def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,default=Path.cwd())
    p.add_argument('--project');p.add_argument('--goal');p.add_argument('--activate',action='store_true');p.add_argument('--db',type=Path,default=default_path())
    p.add_argument('--begin-current',help='JSON work/revision/risk references; user provenance still comes from the host')
    p.add_argument('--finish-current')
    p.add_argument('--update-goals',help='JSON current input reference and exact goal transitions; actual user provenance is read from the host')
    a=p.parse_args(argv)
    try:
        root=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')/'sessions'
        result=run(a.workspace,root,os.environ.get('CODEX_THREAD_ID',''),a.db,project_id=a.project,goal_id=a.goal,activate=a.activate,begin=json.loads(a.begin_current) if a.begin_current else None,finish=a.finish_current,update_goals=json.loads(a.update_goals) if a.update_goals else None)
        print(encoded(result));return 0
    except CoreError as exc:print(encoded(exc.result()));return 2
    except (OSError,ValueError,KeyError) as exc:print(encoded(CoreError('USER_ACTION_REQUIRED',str(exc)).result()));return 2

if __name__=='__main__':raise SystemExit(main())
