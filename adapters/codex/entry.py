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
from .provenance import current_user,infer_operation,is_continuation,proposal_reply
from skip_core.input_contract import normalize,classify


def run(workspace,session_root,thread_id,db_path,*,project_id=None,goal_id=None,activate=False,begin=None,finish=None):
    workspace=workspace.resolve(strict=True)
    user=current_user(session_root,thread_id,workspace)
    project=project_id or resolve_project(workspace,str(workspace),db_path)
    latest_id=user['id']
    if (begin or finish) and is_continuation(user['text']):
        require(re.search(r'계속|진행|\b(continue|proceed)\b',user['text'],re.I),'USER_ACTION_REQUIRED','A status question does not start work')
        with Database(db_path) as existing:
            c=existing.connection
            if begin:
                row=c.execute('SELECT request_id FROM work_item_versions WHERE project_id=? AND id=? AND revision=?',
                    (project,begin['work_id'],begin['revision'])).fetchone()
            else:
                row=c.execute('SELECT w.request_id FROM executions x JOIN work_item_versions w ON w.project_id=x.project_id AND w.id=x.work_item_id AND w.revision=x.work_revision WHERE x.project_id=? AND x.id=?',
                    (project,finish)).fetchone()
            require(row is not None,'NOT_FOUND','Referenced work is unavailable')
            anchor=c.execute('SELECT i.external_event_key FROM requests r JOIN interactions i ON i.project_id=r.project_id AND i.id=r.interaction_id JOIN verified_interactions v ON v.project_id=i.project_id AND v.interaction_id=i.id WHERE r.project_id=? AND r.id=? AND v.verifier=?',
                (project,row['request_id'],'codex-local-session-record')).fetchone()
            require(anchor is not None,'USER_ACTION_REQUIRED','This continuation has no verified request in this Codex conversation')
            user=current_user(session_root,thread_id,workspace,request_id=anchor['external_event_key'])
    identity=('codex',thread_id,user['id'])
    def verify():
        latest=current_user(session_root,thread_id,workspace)
        require(latest['id']==latest_id,'CONTEXT_EXPIRED','The current user turn changed')
        return identity
    origin='codex-input-'+digest([thread_id,user['id']])
    ctx=ExecutionContext(project,{'main':workspace},identity,verify,can_continue=True,context_id=origin,caller_verified=True)
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
            return core.execute(command,principal,ctx)
        if operation=='answer' and re.fullmatch(r'\s*(그래\s*)?(승인이야|승인해|승인|동의해|approve|approved)[.!\s]*',user['text'],re.I):
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
            require(operation in ('plan','implement','investigate','deploy'),'USER_ACTION_REQUIRED','The current user turn must authorize this work')
            op='execution.begin_current' if begin else 'execution.finish_current'
            payload=begin if begin else {'execution_id':finish}
            if begin:
                work=core.query('record',{'kind':'work_item','id':begin['work_id'],'revision':begin['revision']},principal,ctx)['data']
                allowed=set(acts)|{'investigate'}
                if 'implement' in acts:allowed.add('validate')
                require(work['fields']['operation'] in allowed,'USER_ACTION_REQUIRED','Action exceeds the current user request')
            return core.execute({'schema':'skip-core/v1','command':op,'project_id':project,'key':digest([user['id'],op,payload]),'payload':payload},principal,ctx)
        if user['text'].startswith('SKIP 사용자 선택\n'):
            selected=json.loads(user['text'].split('\n',1)[1])
            require(set(selected)=={'schema','project_id','decision_id','revision','option_id'} and selected['schema']=='skip-user-selection/v1'
                    and selected['project_id']==project,'INVALID_INPUT','Invalid selected card')
            p={k:selected[k] for k in ('decision_id','revision','option_id')}
            return core.execute({'schema':'skip-core/v1','command':'decision.select','project_id':project,'key':digest(user['id']),'payload':p},principal,ctx)
        def with_context(result, selected_goal):
            if selected_goal:
                result['data']['context']=core.query('context',{'goal_id':selected_goal,'stage':'restore'},principal,ctx)['data']
            return result
        if envelope['targets']:
            target=envelope['targets'][0]
            selected=core.query('record',target,principal,ctx)['data']
            require(selected['current_revision']==target['revision'],'STALE','Selected record changed')
            require(not goal_id or selected['goal_id']==goal_id,'PROJECT_MISMATCH','Selected record outside goal')
            goal_id=selected['goal_id']
            if operation=='answer':return {'schema':'skip-core/v1','status':'ok','data':{'record':selected,'authority':'reading_material'},'enforcement':'advisory'}
        if operation=='answer' or is_continuation(user['text']):
            return with_context(core.query('status',{'goal_id':goal_id} if goal_id else {},principal,ctx),goal_id)
        require(operation in ('plan','implement','investigate','deploy'),'USER_ACTION_REQUIRED','A concrete current request is needed')
        payload={'text':user['text'],'operation':operation}
        if goal_id:payload['goal_id']=goal_id
        core.execute({'schema':'skip-core/v1','command':'input.ingest','project_id':project,'key':digest([user['id'],'input']),'payload':{}},principal,ctx)
        result=core.execute({'schema':'skip-core/v1','command':'request.submit','project_id':project,'key':digest(user['id']),'payload':payload},principal,ctx)
        request_id=result['data']['request_id']
        body={k:interpretation[k] for k in ('acts','constraints','targets','evidence_spans','unresolved')}
        existing=core.query('entry.inspect',{'request_id':request_id},principal,ctx)['data']['interpretation']
        if existing is None:
            core.execute({'schema':'skip-core/v1','command':'intent.propose','project_id':project,'key':digest([user['id'],'interpretation']),'payload':{'request_id':request_id,'expected_revision':0,'body':body}},principal,ctx)
        result['data']['entry_basis']=core.query('entry.inspect',{'request_id':request_id},principal,ctx)['data']
        result['data']['stage_assessment']=core.query('stage.assess',{'request_id':request_id,'goal_id':result['data']['goal']['id']},principal,ctx)['data']
        return with_context(result,result['data']['goal']['id'])


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--workspace',type=Path,default=Path.cwd())
    p.add_argument('--project');p.add_argument('--goal');p.add_argument('--activate',action='store_true');p.add_argument('--db',type=Path,default=default_path())
    p.add_argument('--begin-current',help='JSON work/revision/risk references; user provenance still comes from the host')
    p.add_argument('--finish-current')
    a=p.parse_args(argv)
    try:
        root=Path(os.environ.get('CODEX_HOME') or Path.home()/'.codex')/'sessions'
        result=run(a.workspace,root,os.environ.get('CODEX_THREAD_ID',''),a.db,project_id=a.project,goal_id=a.goal,activate=a.activate,begin=json.loads(a.begin_current) if a.begin_current else None,finish=a.finish_current)
        print(encoded(result));return 0
    except CoreError as exc:print(encoded(exc.result()));return 2
    except (OSError,ValueError,KeyError) as exc:print(encoded(CoreError('USER_ACTION_REQUIRED',str(exc)).result()));return 2

if __name__=='__main__':raise SystemExit(main())
