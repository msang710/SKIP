"""Authorized local cutover. Existing files become inactive rollback originals."""
from pathlib import Path
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import tarfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import yaml
from tools.migrate_records import inventory,migrate
from skip_core.db import Database
from skip_core.service import Core
from skip_core.authority import Principal

repo=Path(__file__).resolve().parents[1]
state=json.loads((repo/'.build/deployment-state.json').read_text())
root,backup,release=(Path(state[k]) for k in ('root','backup','release'))
assert state['status']=='STAGED_NOT_ACTIVE'
assert not (root/'skip.db').exists()
manifest=json.loads((release/'release-manifest.json').read_text())
for name,checksum in manifest.items():assert hashlib.sha256((release/name).read_bytes()).hexdigest()==checksum
old=inventory(root)
with tarfile.open(backup/'records-before.tar.gz','r:gz') as archive:
    for row in old['files']:
        member=archive.extractfile(row['path'])
        assert member and hashlib.sha256(member.read()).hexdigest()==row['sha256'],'Source changed since backup; prepare a fresh backup'
subprocess.run(['paseo','plugin','disable','intent-launcher','--host','127.0.0.1:6767','--json'],check=True)
# Removing the old active directory freezes path-based discovery before import.
(root/'projects').rename(backup/'projects')
try:
    candidate=root/'skip.migrating.db'
    registry=yaml.safe_load((backup/'workspaces.yaml').read_text())
    report=migrate(backup,candidate,old,registry)
    with Database(candidate) as db:
        assert db.connection.execute('SELECT count(*) FROM imported_documents').fetchone()[0]==len(old['files'])
        for project in report['projects']:
            result=Core(db).query('status',{'limit':2},Principal(project['project_id'],'deployment-validation'))
            assert result['status']=='ok'
    assert inventory(backup)['digest']==old['digest']
except BaseException:
    (backup/'projects').rename(root/'projects')
    subprocess.run(['paseo','plugin','enable','intent-launcher','--host','127.0.0.1:6767','--json'],check=False)
    raise
# The old readers stay available only as rollback artifacts, outside skill discovery.
installed=Path.home()/'.agents/skills/skip'
installed.rename(backup/'installed-skip')
for path in list(installed.parent.glob('skip.backup-*')):
    path.rename(backup/path.name)
plugin=Path.home()/'IntentPlugins/intent-launcher'
plugin.rename(backup/'installed-paseo-plugin')
current=root/'runtime/current'
assert not current.exists()
current.symlink_to(release,target_is_directory=True)
installed.symlink_to(current,target_is_directory=True)
plugin.symlink_to(current/'plugins/paseo',target_is_directory=True)
os.rename(candidate,root/'skip.db')
(root/'skip.db').chmod(0o600)
# launchers keep the caller's project cwd; they never cd into the skill root.
bin_root=Path.home()/'.local/bin';bin_root.mkdir(parents=True,exist_ok=True)
for name,module in [('skip','skip_core.cli'),('skip-mcp','skip_mcp.server'),('skip-codex','adapters.codex.entry')]:
    path=bin_root/name
    assert not path.exists(),'Unexpected existing launcher: '+str(path)
    text='#!/bin/sh\nSKIP_RELEASE='+shlex.quote(str(current))+'\nexport PYTHONPATH="$SKIP_RELEASE"\nexec "$SKIP_RELEASE/.venv/bin/python" -B -m '+module+' "$@"\n'
    path.write_text(text);path.chmod(0o755)
state.update(status='ACTIVATED_AWAITING_LIVE_CHECK',migration=report)
(repo/'.build/deployment-state.json').write_text(json.dumps(state,ensure_ascii=False,indent=2)+'\n')
(backup/'migration-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
subprocess.run(['paseo','plugin','enable','intent-launcher','--host','127.0.0.1:6767','--json'],check=True)
print(json.dumps(state,ensure_ascii=False))
