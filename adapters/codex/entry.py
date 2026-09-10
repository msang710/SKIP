"""Use the current Codex user turn. Never launch an unrelated app-server session."""
import argparse
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
from .provenance import current_user,infer_operation,is_continuation


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
    ctx=ExecutionContext(project,{'main':workspace},identity,verify,can_continue=True,context_id=origin)
    # Stable per selected host user turn; process restarts do not invent a new request.
    principal=Principal(project,origin,kind='human',method='host_user_turn',
                        verifier='codex-local-session-record',event_key=user['id'],user_text=user['text'])
    operation=infer_operation(user['text'])
    if activate:
        require(re.search(r'(?<!\w)[/$]skip\b|\bSKIP\b',user['text'],re.I),'USER_ACTION_REQUIRED','Activation requires an explicit SKIP request')
    with Database(db_path,create=activate) as db:
        core=Core(db)
        if activate:
            command={'schema':'skip-core/v1','command':'project.activate','project_id':project,'key':digest([user['id'],'activate']),
                     'payload':{'name':workspace.name}}
            return core.execute(command,principal,ctx)
        if begin or finish:
            require(operation in ('plan','implement'),'USER_ACTION_REQUIRED','The current user turn must authorize this work')
            op='execution.begin_current' if begin else 'execution.finish_current'
            payload=begin if begin else {'execution_id':finish}
            if begin:
                work=core.query('record',{'kind':'work_item','id':begin['work_id'],'revision':begin['revision']},principal,ctx)['data']
                allowed=('investigate','requirements','design','tasks') if operation=='plan' else ('investigate','implement','validate')
                require(work['fields']['operation'] in allowed,'USER_ACTION_REQUIRED','Action exceeds the current user request')
            return core.execute({'schema':'skip-core/v1','command':op,'project_id':project,'key':digest([user['id'],op,payload]),'payload':payload},principal,ctx)
        if user['text'].startswith('SKIP 사용자 선택\n'):
            selected=json.loads(user['text'].split('\n',1)[1])
            require(set(selected)=={'schema','project_id','decision_id','revision','option_id'} and selected['schema']=='skip-user-selection/v1'
                    and selected['project_id']==project,'INVALID_INPUT','Invalid selected card')
            p={k:selected[k] for k in ('decision_id','revision','option_id')}
            return core.execute({'schema':'skip-core/v1','command':'decision.select','project_id':project,'key':digest(user['id']),'payload':p},principal,ctx)
        if operation=='answer' or is_continuation(user['text']):
            return core.query('status',{'goal_id':goal_id} if goal_id else {},principal,ctx)
        require(operation in ('plan','implement'),'USER_ACTION_REQUIRED','A concrete current request is needed')
        payload={'text':user['text'],'operation':operation}
        if goal_id:payload['goal_id']=goal_id
        return core.execute({'schema':'skip-core/v1','command':'request.submit','project_id':project,'key':digest(user['id']),'payload':payload},principal,ctx)


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
