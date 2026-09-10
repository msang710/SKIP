"""Explicit candidate upgrade: never migrate or replace the active DB on a read."""
import os
import sqlite3
from pathlib import Path
from .db import Database
from .errors import require

def candidate(source,destination):
    source=Path(source).absolute();destination=Path(destination).absolute()
    require(source!=destination and source.is_file() and not source.is_symlink(),'INVALID_INPUT','Select an existing source and a new destination')
    fd=os.open(destination,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600);os.close(fd)
    old=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    new=sqlite3.connect(destination)
    try:
        expected={v:sha for v,_,sha in Database.migrations()}
        actual=old.execute('SELECT version,checksum FROM schema_migrations ORDER BY version').fetchall()
        require(actual and [v for v,_ in actual]==list(range(1,len(actual)+1)) and all(expected.get(v)==sha for v,sha in actual),'UNSUPPORTED_SCHEMA','Unknown source migration/checksum')
        old.backup(new)
        require(new.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not new.execute('PRAGMA foreign_key_check').fetchall(),'RECOVERY_REQUIRED','Backup integrity failed')
        captured_sequence=new.execute('SELECT COALESCE(max(sequence),0) FROM events').fetchone()[0]
    finally:
        old.close();new.close()
    with Database(destination,create=True) as upgraded:
        require(upgraded.connection.execute('PRAGMA integrity_check').fetchone()[0]=='ok' and not upgraded.connection.execute('PRAGMA foreign_key_check').fetchall(),'RECOVERY_REQUIRED','Upgrade integrity failed')
    return {'status':'candidate_ready','path':str(destination),'activated':False,'captured_sequence':captured_sequence,
            'notice':'Stop writers and recheck the source before any separate cutover. This candidate does not include later writes.'}
