"""Scoped, DB-only MCP tools and resources. No model-callable approval tool."""
import argparse
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from skip_core.authority import Principal,ExecutionContext
from skip_core.common import encoded,uid
from skip_core.db import Database,default_path
from skip_core.errors import CoreError,require
from skip_core.service import Core
from .authoring_types import AuthoringBase, Submission, Amendment, ResultEvidence, CurrentFact, FailureReport


def create_server(db_path,project_id,workspace=None,receipt_scope=None):
    from adapters.common.caller import caller_scope
    caller, verified = caller_scope(workspace, 'mcp', receipt_scope) if workspace else (uid(), False)
    principal=Principal(project_id,caller)
    root = Path(workspace).resolve(strict=True) if workspace else None
    def observe_source():
        value = root.stat()
        return ('mcp', str(root.resolve(strict=True)), str(value.st_dev), str(value.st_ino))
    identity = observe_source() if root else ()
    source_context = ExecutionContext(project_id, {'main':root}, identity, observe_source,
        caller_verified=verified, renewable_source=True) if root else None
    def refresh():
        if verified:
            current, still_verified = caller_scope(workspace, 'mcp', receipt_scope)
            require(still_verified and current == caller, 'CALLER_UNVERIFIED', 'Current host caller could not be revalidated')
        if source_context:
            try: source_context.refresh_source()
            except OSError as exc:
                raise CoreError('SOURCE_UNAVAILABLE', 'Configured source is unavailable') from exc
    # Open/close per operation: no daemon, no automatically created DB, no shared
    # SQLite connection across SDK thread/task boundaries.
    def query(name,p):
        try:
            refresh()
            with Database(db_path) as db:return Core(db).query(name,p,principal,source_context)
        except CoreError as exc:return exc.result()
    def command(op,p,key):
        try:
            refresh()
            with Database(db_path) as db:
                return Core(db).execute({'schema':'skip-core/v1','project_id':project_id,'command':op,'key':key,'payload':p},principal,source_context)
        except CoreError as exc:return exc.result()
    server=FastMCP('SKIP',instructions='Read product decisions and current evidence. Tools cannot confer human approval or start a different agent. Gate enforcement is advisory.')
    read=ToolAnnotations(readOnlyHint=True,destructiveHint=False,idempotentHint=True,openWorldHint=False)

    @server.tool(annotations=read)
    async def skip_learning(query_name:str,payload:dict)->dict:
        """Read learning.list, learning.record, guidance or assurance through Core."""
        if query_name not in ('failure.history','learning.list','learning.record','guidance','assurance'):
            return {'status':'error','code':'INVALID_INPUT','enforcement':'advisory'}
        return query(query_name,payload)

    @server.tool()
    async def skip_record_learning(operation:str,payload:dict,key:str)->dict:
        """Record failures, candidate guidelines, assessments or verification. Cannot accept contracts."""
        from skip_core.learning_runtime import OPS
        if operation not in OPS or OPS[operation][2]:
            return {'status':'error','code':'USER_ACTION_REQUIRED','enforcement':'advisory'}
        return command(operation,payload,key)

    @server.tool(annotations=read)
    async def skip_entry(request_id:str, goal_id:str|None=None, assess_stage:bool=False)->dict:
        """Read input provenance or stage requirements; never grants authority."""
        return query('stage.assess' if assess_stage else 'entry.inspect',{'request_id':request_id,**({'goal_id':goal_id} if goal_id and assess_stage else {})})

    @server.tool()
    async def skip_interpret(request_id:str,expected_revision:int,body:dict,key:str)->dict:
        """Propose intent with original instruction spans; cannot grant user authority."""
        return command('intent.propose',{'request_id':request_id,'expected_revision':expected_revision,'body':body},key)

    @server.tool()
    async def skip_propose_action(request_id:str,body:dict,key:str,id:str|None=None,expected_revision:int=0)->dict:
        """Prepare exact action/scope for a native reply; display_ref must accompany the shown proposal. Not approval."""
        return command('action.propose',{'request_id':request_id,'body':body,'expected_revision':expected_revision,**({'id':id} if id else {})},key)

    @server.tool()
    async def skip_submit(base:AuthoringBase,records:list[Submission],submission_id:str)->dict:
        """Atomically create linked records. Each has client_ref, kind, fields, children. Refer to earlier records as $client_ref; revisions are resolved by Core. No approvals."""
        return command('authoring.submit',{'base':base,'records':records},submission_id)

    @server.tool()
    async def skip_amend(base:AuthoringBase,changes:list[Amendment],submission_id:str)->dict:
        """Patch exact target {kind,id,revision} using set_fields/upsert_items/remove_items. Omitted fields and links survive. Atomic; receipt includes saved records."""
        return command('authoring.amend',{'base':base,'changes':changes},submission_id)

    @server.tool()
    async def skip_result(base:AuthoringBase,snapshot_id:str,evidence:ResultEvidence,submission_id:str,execution_id:str|None=None,now:CurrentFact|None=None,failure:FailureReport|None=None)->dict:
        """Record evidence and optional explicit NOW/failure together. Ordinary FAIL is evidence only; failure opts into an incident. Never marks execution finished."""
        return command('authoring.result',{'base':base,'snapshot_id':snapshot_id,'evidence':evidence,**({'execution_id':execution_id} if execution_id else {}),**({'now':now} if now else {}),**({'failure':failure} if failure else {})},submission_id)

    @server.tool(annotations=read)
    async def skip_requests(goal_id:str|None=None,cursor:str|None=None,limit:int=30)->dict:
        """Read requests saved in SKIP (including UI submissions), not the latest chat message."""
        return query('request.list',{'goal_id':goal_id,'cursor':cursor,'limit':limit})

    @server.tool(annotations=read)
    async def skip_request(id:str)->dict:
        """Read one exact saved request and its linked goals; reading grants no execution authority."""
        return query('request',{'id':id})

    @server.tool(annotations=read)
    async def skip_status(goal_id:str|None=None,cursor:str|None=None,limit:int=30)->dict:
        """Current facts, checks and remaining work; never creates a goal."""
        return query('status',{'goal_id':goal_id,'cursor':cursor,'limit':limit})

    @server.tool(annotations=read)
    async def skip_context(goal_id:str,stage:str='implementation',budget:int=18000,snapshot_id:str|None=None,work_id:str|None=None,request_id:str|None=None)->dict:
        """Bounded goal context. Incomplete means required context was omitted."""
        return query('context',{'goal_id':goal_id,'stage':stage,'budget':budget,**({'snapshot_id':snapshot_id} if snapshot_id else {}),**({'work_id':work_id} if work_id else {}),**({'request_id':request_id} if request_id else {})})

    @server.tool(annotations=read,meta={'ui':{'resourceUri':'ui://skip/decision-inbox'}})
    async def skip_decisions(goal_id:str|None=None,cursor:str|None=None,limit:int=30)->dict:
        """Read exact-version product questions and selections."""
        return query('inbox',{'goal_id':goal_id,'cursor':cursor,'limit':limit})

    @server.tool()
    async def skip_propose(kind:str,request_id:str,goal_id:str,fields:dict,children:dict,
                           key:str,expected_revision:int=0,id:str|None=None)->dict:
        """Propose a typed record revision linked to an actual request. This is not approval."""
        p={'kind':kind,'request_id':request_id,'goal_id':goal_id,'fields':fields,'children':children,'expected_revision':expected_revision}
        if id:p['id']=id
        return command('record.propose_revision',p,key)

    @server.tool()
    async def skip_assess_risk(goal_id:str,paths:list[dict],goal_factors:dict,change_factors:dict,rationale:str,key:str)->dict:
        """Record explicit goal and change risk against the current source snapshot."""
        return command('risk.assess',dict(goal_id=goal_id,paths=paths,goal_factors=goal_factors,change_factors=change_factors,rationale=rationale),key)

    @server.tool()
    async def skip_record_result(payload:dict,key:str)->dict:
        """Record evidence as agent_report; cannot certify host observations or finish a turn."""
        return command('evidence.record',payload,key)

    @server.tool()
    async def skip_observe(paths:list[dict],summary:str,key:str,goal_id:str|None=None)->dict:
        """Measure a read-only scope for current evidence; creates no goal."""
        return command('observation.record',{'paths':paths,'summary':summary,**({'goal_id':goal_id} if goal_id else {})},key)

    @server.tool(annotations=read)
    async def skip_execution_status(execution_id:str)->dict:
        """Separate delivery, execution and verification state."""
        return query('execution.status',{'execution_id':execution_id})

    @server.tool(annotations=read)
    async def skip_records(goal_id:str|None=None,kind:str|None=None,cursor:str|None=None,limit:int=30,search:str|None=None)->dict:
        """List native decisions, requirements, plans, work and evidence."""
        return query('record.list',{k:v for k,v in {'goal_id':goal_id,'kind':kind,'cursor':cursor,'limit':limit,'search':search}.items() if v is not None})

    @server.tool(annotations=read)
    async def skip_record(kind:str,id:str,revision:int|None=None)->dict:
        """Read an exact native record, original status and relationships."""
        return query('record',{k:v for k,v in {'kind':kind,'id':id,'revision':revision}.items() if v is not None})

    @server.tool()
    async def skip_history(goal_id:str|None=None,cursor:str|None=None,limit:int=30,search:str|None=None)->dict:
        """Read imported historical records; they are not current execution authority."""
        return query('history',{k:v for k,v in {'goal_id':goal_id,'cursor':cursor,'limit':limit,'search':search}.items() if v is not None})

    @server.tool()
    async def skip_history_record(id:str,offset:int=0,length:int=16000)->dict:
        """Read an exact original, relationships and historical status from SQLite."""
        return query('history.record',{'id':id,'offset':offset,'length':length})

    @server.resource('skip://projects/{project}/now',mime_type='application/json')
    async def current(project:str)->str:
        require(project==project_id,'PROJECT_MISMATCH','Project is outside this connection')
        return encoded(query('status',{}))

    @server.resource('skip://projects/{project}/goals/{goal}/context',mime_type='application/json')
    async def context(project:str,goal:str)->str:
        require(project==project_id,'PROJECT_MISMATCH','Project is outside this connection')
        return encoded(query('context',{'goal_id':goal,'stage':'implementation'}))

    @server.resource('skip://projects/{project}/records/{kind}/{id}/{revision}',mime_type='application/json')
    async def record(project:str,kind:str,id:str,revision:str)->str:
        require(project==project_id,'PROJECT_MISMATCH','Project is outside this connection')
        return encoded(query('record',{'kind':kind,'id':id,'revision':int(revision)}))

    @server.resource('ui://skip/decision-inbox',mime_type='text/html;profile=mcp-app',
                     meta={'ui':{'csp':{'connectDomains':[],'resourceDomains':[]}}})
    async def inbox_ui()->str:
        return (Path(__file__).parents[1]/'ui/mcp-app/dist/index.html').read_text()
    return server


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,default=default_path());p.add_argument('--project')
    p.add_argument('--receipt-scope',help='Client-owned retry namespace, not execution authority')
    p.add_argument('--workspace',type=Path,default=Path.cwd());a=p.parse_args()
    if a.project is None:
        from adapters.common.identity import resolve_project
        a.project=resolve_project(a.workspace,str(a.workspace),a.db)
    create_server(a.db,a.project,a.workspace,a.receipt_scope).run(transport='stdio')

if __name__=='__main__':main()
