"""DB-only CLI. Piped/model commands never acquire human authority."""
import argparse
import json
import sys
from pathlib import Path
from .authority import Principal,ExecutionContext
from .common import encoded,uid
from .db import Database,default_path,restore
from .errors import CoreError,require
from .service import Core


def main(argv=None):
    parser=argparse.ArgumentParser(description='SKIP: read decisions, keep your agent and IDE')
    parser.add_argument('--db',type=Path,default=default_path())
    parser.add_argument('--project')
    parser.add_argument('--receipt-scope', help='Client-owned retry namespace; never user or execution authority')
    parser.add_argument('--workspace',type=Path,default=Path.cwd())
    sub=parser.add_subparsers(dest='operation',required=True)
    sub.add_parser('diagnose',help='Report the active Core, DB path and schema compatibility')
    sub.add_parser('activate',help='Interactively connect this project; creates no goals')
    query=sub.add_parser('query');query.add_argument('name');query.add_argument('--input',default='{}')
    sub.add_parser('command',help='Read an agent command from stdin; cannot approve or start a turn')
    sub.add_parser('request',help='Read a real request interactively')
    backup=sub.add_parser('backup');backup.add_argument('target',type=Path)
    restore_parser=sub.add_parser('restore');restore_parser.add_argument('target',type=Path)
    args=parser.parse_args(argv)
    try:
        if args.operation=='diagnose':
            with Database(args.db) as db:
                print(encoded({'status':'ok', **db.diagnostics([r[0] for r in db.connection.execute('SELECT version FROM schema_migrations ORDER BY version')])}))
            return 0
        if args.operation=='restore':
            print(encoded(restore(args.db,args.target)));return 0
        if args.project is None:
            from adapters.common.identity import resolve_project
            args.project=resolve_project(args.workspace,str(args.workspace),args.db)
        context=None
        if args.workspace:
            root=args.workspace.resolve(strict=True)
            context=ExecutionContext(args.project,{'main':root},('cli',),lambda:('cli',))
        from adapters.common.caller import caller_scope
        caller, verified = caller_scope(args.workspace, 'cli', args.receipt_scope)
        if context: context.caller_verified = verified
        principal=Principal(args.project,caller)
        if args.operation in ('activate','request'):
            require(sys.stdin.isatty() and sys.stdout.isatty(),'USER_ACTION_REQUIRED','Use the native app or an interactive user terminal')
            require(context is not None,'CONTEXT_EXPIRED','Current workspace is required')
            prompt='Connect this project? Type connect: ' if args.operation=='activate' else 'What should SKIP do? '
            words=input(prompt).strip()
            require(words=='connect' if args.operation=='activate' else bool(words),'USER_ACTION_REQUIRED','No user request received')
            principal=Principal(args.project,context.context_id,kind='human',method='interactive_tty',verifier='interactive-cli',event_key=uid(),user_text=words)
        with Database(args.db,create=args.operation=='activate') as db:
            core=Core(db)
            if args.operation=='query':
                result=core.query(args.name,json.loads(args.input),principal,context)
            elif args.operation=='backup':
                result=db.backup(args.target)
            else:
                if args.operation=='command':
                    require(verified or args.receipt_scope, 'CALLER_UNVERIFIED',
                            'No verified caller for retry-safe commands; configure a client-owned --receipt-scope. This grants no approval.')
                    raw=sys.stdin.read(512001)
                    require(len(raw)<=512000,'INVALID_INPUT','Command too large')
                    command=json.loads(raw)
                else:
                    op='project.activate' if args.operation=='activate' else 'request.submit'
                    payload={'name':args.project} if args.operation=='activate' else {'text':words,'operation':'implement'}
                    command={'schema':'skip-core/v1','command':op,'key':uid(),'project_id':args.project,'payload':payload}
                result=core.execute(command,principal,context)
        print(encoded(result)); return 0
    except CoreError as exc:
        print(encoded(exc.result()));return 2
    except (ValueError,OSError,KeyError) as exc:
        print(encoded(CoreError('INVALID_INPUT',str(exc)).result()));return 2

if __name__=='__main__':raise SystemExit(main())
