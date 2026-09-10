import hashlib
import re
import subprocess
from pathlib import Path


def project_identity(workspace, fallback):
    try:
        raw=subprocess.run(['git','-C',str(workspace),'config','--get','remote.origin.url'],capture_output=True,
                           timeout=3,check=True,text=True).stdout.strip()
        value=re.sub(r'^[\w+.-]+://(?:[^/@]+@)?','',raw)
        value=re.sub(r'^[^/@]+@','',value)
        value=re.sub(r'^([^/]+):',r'\1/',value)
        value=re.sub(r'\.git/?$','',value).rstrip('/')
        if value and not value.startswith('/') and '/' in value:
            return 'repo-'+hashlib.sha256(value.encode()).hexdigest()[:24]
    except (OSError,subprocess.SubprocessError):
        pass
    return 'project-'+hashlib.sha256(fallback.encode()).hexdigest()[:24]


def resolve_project(workspace, fallback, db_path=None):
    """Match portable repository identities, never saved IDE/agent bindings."""
    import json
    from skip_core.db import Database,default_path
    from skip_core.errors import require
    path=Path(db_path) if db_path else default_path()
    if not path.is_file():return project_identity(workspace,fallback)
    workspace=Path(workspace).resolve(strict=True)
    with Database(path) as db:
        aliases=db.connection.execute('SELECT project_id,repository_identity,relative_root FROM project_identities').fetchall()
        require(len(aliases)<=512,'INVALID_INPUT','Too many project identities')
        found=set();cache={}
        for row in aliases:
            relative=Path(row['relative_root'])
            if relative.is_absolute() or '..' in relative.parts:continue
            candidate=(workspace/relative).resolve()
            if not candidate.is_relative_to(workspace) or not candidate.is_dir():continue
            if candidate not in cache:
                cache[candidate]=project_identity(candidate,'unmatched')
            expected='repo-'+hashlib.sha256(row['repository_identity'].encode()).hexdigest()[:24]
            if cache[candidate]==expected:found.add(row['project_id'])
        require(len(found)<=1,'PROJECT_MISMATCH','Multiple project identities match this workspace')
        return next(iter(found)) if found else project_identity(workspace,fallback)


if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser();parser.add_argument('--workspace',type=Path,required=True);parser.add_argument('--fallback',required=True);parser.add_argument('--db',type=Path)
    args=parser.parse_args()
    print(json.dumps({'project_id':resolve_project(args.workspace,args.fallback,args.db)}))
