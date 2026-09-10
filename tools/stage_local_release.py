"""Prepare a local release and rollback backup without activating either."""
from pathlib import Path
import datetime
import hashlib
import json
import shutil
import tarfile
import subprocess
import sys

source=Path(__file__).resolve().parents[1]
base=Path.home()/'.local/share/SKIP'
stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
backup=base/'backups'/stamp
release=base/'runtime/releases'/stamp
backup.mkdir(parents=True,exist_ok=False,mode=0o700)
with tarfile.open(backup/'records-before.tar.gz','x:gz') as out:
    for name in ('projects','.migration-archive-20260831','.retired-roots'):
        if (base/name).exists():out.add(base/name,arcname=name,recursive=True)
for origin,name in [(Path.home()/'.config/intent-to-code/workspaces.yaml','workspaces.yaml'),(Path.home()/'.codex/config.toml','codex-config.toml'),(Path.home()/'.paseo/config.json','paseo-config.json')]:
    if origin.is_file():shutil.copy2(origin,backup/name)
release.mkdir(parents=True,mode=0o700)
for directory in ('skip_core','skip_mcp','adapters','schemas'):
    shutil.copytree(source/directory,release/directory,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
for path in ('SKILL.md','agents/openai.yaml','references/db-core-contract.md','ui/mcp-app/dist/index.html','requirements/core.txt'):
    target=release/path;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source/path,target)
plugin=release/'plugins/paseo';plugin.mkdir(parents=True)
for name in ('index.ts','core.panel.client.tsx','core.record.client.tsx','records.document.tsx','core.overview.ts','core.bridge.server.ts','session-routing.server.ts','turn-receipt.ts','core.shared.ts','core.invocations.ts','intent.shared.ts','paseo-plugin.json','paseo-plugin.d.ts','tsconfig.json','package.json','package-lock.json'):
    shutil.copy2(source/'plugins/paseo'/name,plugin/name)
manifest={p.relative_to(release).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in release.rglob('*') if p.is_file()}
(release/'release-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
state={'source':str(source),'root':str(base),'backup':str(backup),'release':str(release),'files':len(manifest),'status':'STAGED_NOT_ACTIVE'}
(source/'.build/deployment-state.json').write_text(json.dumps(state,indent=2)+'\n')
subprocess.run([sys.executable,'-m','venv',str(release/'.venv')],check=True)
subprocess.run([str(release/'.venv/bin/python'),'-m','pip','install','--disable-pip-version-check','-r',str(release/'requirements/core.txt')],check=True,stdout=subprocess.DEVNULL)
print(json.dumps(state))
