"""Offline correction of the initial import, never an agent/runtime command.

Only historical imports without execution/approval state can be moved. The
explicitly authorized maintenance operation preserves sealed bodies and goal IDs;
project ownership and original-path namespace change atomically. Triggers are
restored before integrity checks and commit. Every attempt requires a backup.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import uuid
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from skip_core.db import Database
from skip_core.common import now, digest

ALLOWED = {'sources','interactions','verified_interactions','requests','events',
    'goals','goal_versions','requirements','requirement_versions','plans',
    'plan_versions','acceptance_criteria','plan_items','request_goals',
    'imported_documents','imported_sections','imported_links','imported_record_refs',
    'project_identities'}

def q(value):
    return '"'+value.replace('"','""')+'"'

def merge(path, source, target, backup):
    assert source != target
    backup = Path(backup)
    assert not backup.exists(), 'Backup must be new'
    with Database(path) as db:
        c = db.connection
        b = sqlite3.connect(backup)
        try: c.backup(b)
        finally: b.close()
        backup.chmod(0o600)
        with db.transaction():
            c.execute('PRAGMA defer_foreign_keys=ON')
            assert c.execute('select count(*) from projects where id in (?,?)',(source,target)).fetchone()[0] == 2
            before = {(r['project_id'],r['id']): bytes(r['content']) for r in c.execute('select * from imported_documents')}
            tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
            affected = []
            for table in tables:
                cols = [r['name'] for r in c.execute('pragma table_info('+q(table)+')')]
                if 'project_id' in cols and c.execute('select 1 from '+q(table)+' where project_id=?',(source,)).fetchone():
                    assert table in ALLOWED, 'Nonhistorical state: '+table
                    affected.append(table)
            for kind in ('requirements','plans'):
                assert not c.execute('select 1 from '+kind+' where project_id=? and lifecycle<>?',(source,'held')).fetchone()
            assert c.execute('select count(*) from imported_documents where project_id=?',(source,)).fetchone()[0] > 0
            assert not c.execute('select 1 from goals s join goals t on s.id=t.id where s.project_id=? and t.project_id=?',(source,target)).fetchone(), 'Goal collision requires explicit resolution'
            # Preserve every sealed field. Only maintenance ownership metadata is changed.
            triggers = [(r['name'],r['sql']) for r in c.execute("select name,sql,tbl_name from sqlite_master where type='trigger'") if r['tbl_name'] in affected]
            for name,_ in triggers: c.execute('drop trigger '+q(name))
            c.execute('update interactions set external_event_key=?||external_event_key where project_id=?',(source+'/',source))
            c.execute('update events set command_key=?||command_key where project_id=?',(source+'/',source))
            offset = c.execute('select coalesce(max(sequence),0) from events where project_id=?',(target,)).fetchone()[0]
            c.execute('update events set sequence=sequence+? where project_id=?',(offset,source))
            # Retain original relative paths in an explicit historical project namespace.
            prefix = 'merged/'+source+'/'
            doc_prefix = source+'-'
            c.execute('update imported_documents set id=?||id where project_id=?',(doc_prefix,source))
            for table in ('imported_sections','imported_links','imported_record_refs'):
                c.execute('update '+q(table)+' set document_id=?||document_id where project_id=?',(doc_prefix,source))
            c.execute('update imported_links set target_document_id=?||target_document_id where project_id=? and target_document_id is not null',(doc_prefix,source))
            c.execute('update imported_documents set source_path=?||source_path where project_id=?',(prefix,source))
            # These imported sources have no snapshots or other source references.
            c.execute('update sources set id=?||id,name=?||name where project_id=?',(source+'/',source+'/',source))
            counts = {}
            for table in affected:
                counts[table] = c.execute('update '+q(table)+' set project_id=? where project_id=?',(target,source)).rowcount
            c.execute('delete from projects where id=?',(source,))
            for _,sql in triggers: c.execute(sql)
            assert not c.execute('pragma foreign_key_check').fetchall()
            assert c.execute('pragma integrity_check').fetchone()[0] == 'ok'
            after = {(r['project_id'],r['id']): bytes(r['content']) for r in c.execute('select * from imported_documents')}
            expected = {(target if p==source else p,doc_prefix+i if p==source else i):v for (p,i),v in before.items()}
            assert after == expected, 'Historical originals changed'
            for row in c.execute('select content,content_sha256 from imported_documents'):
                assert hashlib.sha256(row[0]).hexdigest()==row[1]
            stamp=now(); interaction=uuid.uuid4().hex; event=uuid.uuid4().hex
            body='User requested merging NEON Greeter records into NEON; offline import correction. No authority granted.'
            c.execute('insert into interactions values(?,?,?,?,?,?,?,?)',(target,interaction,digest({'maintenance':source,'target':target}),event,'agent',body,hashlib.sha256(body.encode()).hexdigest(),stamp))
            payload={'source_project':source,'target_project':target,'moved_rows':counts,'original_bytes_preserved':True,'path_prefix':prefix}
            seq=c.execute('select max(sequence)+1 from events where project_id=?',(target,)).fetchone()[0]
            c.execute('insert into events values(?,?,?,?,?,?,?,?,?)',(target,event,seq,interaction,event,digest(payload),'maintenance.historical_project_merged',json.dumps(payload),stamp))
            assert not c.execute('pragma foreign_key_check').fetchall()
            return payload

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--source',required=True);p.add_argument('--target',required=True);p.add_argument('--backup',required=True)
    a=p.parse_args();print(json.dumps(merge(a.db,a.source,a.target,a.backup),ensure_ascii=False))
