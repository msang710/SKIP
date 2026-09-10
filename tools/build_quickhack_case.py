"""Build the public case from exactly four reviewed excerpts, never the live DB.

The SQLite artifact is the migrated record store. records.md is a generated,
read-only publication view of Core queries, not a second editable business store.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import migrate_records
from tools.reimport_records import repair
from skip_core.db import Database
from skip_core.service import Core
from skip_core.authority import Principal

GOAL = 'manual-order-inventory-matching'
PROJECT = 'quickhack-public-case'
FILES = ('prd.md', 'user_stories.md', 'system_design.md', 'tasks.md')
ROOT = Path(__file__).resolve().parents[1]
LABELS = {'goal':'목표', 'decision':'제품 결정', 'requirement':'요구사항', 'plan':'설계', 'work_item':'작업', 'evidence':'근거·검증'}


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    target = output / 'case.db'
    if target.exists():
        raise SystemExit('Refusing to overwrite an existing case.db; use a fresh output directory.')
    with tempfile.TemporaryDirectory(prefix='skip-public-case-') as tmp:
        root = Path(tmp)
        folder = root / 'projects' / PROJECT / 'features' / GOAL
        folder.mkdir(parents=True)
        for name in FILES:
            shutil.copyfile(ROOT / 'examples/quickhack' / name, folder / name)
        migrate_records.REQUEST = '바로 반영해 사례에 제시한 goal에 포함된 문서들만 마이그레이션 해'
        imported = migrate_records.migrate(root, target, migrate_records.inventory(root))
    report = repair(target)
    with Database(target) as db:
        c = db.connection
        assert [r[0] for r in c.execute('SELECT id FROM projects')] == [PROJECT]
        assert [r[0] for r in c.execute('SELECT id FROM goals')] == [GOAL]
        docs = list(c.execute('SELECT source_path,content,content_sha256 FROM imported_documents'))
        assert {Path(r[0]).name for r in docs} == set(FILES) and len(docs) == 4
        for path, blob, sha in docs:
            assert bytes(blob) == (ROOT / 'examples/quickhack' / Path(path).name).read_bytes()
            assert hashlib.sha256(blob).hexdigest() == sha
        for table in ('authorizations', 'selections', 'executions', 'evidence'):
            assert c.execute('SELECT count(*) FROM '+table).fetchone()[0] == 0
        assert not c.execute('PRAGMA foreign_key_check').fetchall()
        assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        core = Core(db)
        principal = Principal(PROJECT, 'public-case-read')
        items = []
        payload = {'goal_id':GOAL, 'limit':100}
        while True:
            page = core.query('record.list', payload, principal)['data']
            items.extend(page['items'])
            if not page['next_cursor']: break
            payload['cursor'] = page['next_cursor']
        entries = [core.query('record', {'kind':'goal', 'id':GOAL}, principal)['data']]
        entries += [core.query('record', {'kind':i['kind'], 'id':i['id'], 'revision':i['revision']}, principal)['data'] for i in items]
        def key(r): return (r['origin'] or {}).get('source_key') or r['id']
        entries.sort(key=lambda r: (list(LABELS).index(r['kind']), key(r)))
        anchors = {r['id']: 'record-'+str(i) for i,r in enumerate(entries)}
        lines = ['# QuickHack — 이관된 목표 기록', '',
                 '[사례 안내](README.md) · [사례 DB](case.db) · [이관 검증](migration.json)', '',
                 '> 현재 Core의 record.list / record 조회 결과로 생성한 읽기 전용 공개 뷰입니다. 수정 원본은 사례 DB입니다. 과거 발췌 기록의 이관이며 현재 승인·검증 결과가 아닙니다.', '',
                 '> Read-only publication view generated from Core queries. Migrated historical excerpts, not fresh approval or verification.', '',
                 '## 기록 목록', '', '| 유형 | 기록 | 당시 상태 |', '|---|---|---|']
        for r in entries:
            status = (r['origin'] or {}).get('source_status', 'UNSPECIFIED')
            lines.append(f"| {LABELS[r['kind']]} | [{key(r).replace('|','/')}](#{anchors[r['id']]}) | {status.replace('|','/')} |")
        for r in entries:
            lines += ['', f'<a id="{anchors[r["id"]]}"></a>', '', f'## {LABELS[r["kind"]]} · {key(r)}', '']
            origin = r['origin'] or {}
            lines += [f"기록 revision: {r['revision']} · 당시 상태: {origin.get('source_status', 'UNSPECIFIED')}", '']
            for field, value in r['fields'].items():
                if value:
                    lines += [f'**{field}**', '', str(value), '']
            for group, children in r['children'].items():
                if not children: continue
                lines += [f'### {group}', '']
                for child in children:
                    for field, value in child.items():
                        if value is None or value == '': continue
                        display = str(value)
                        if display in anchors: display = f'[{display}](#{anchors[display]})'
                        lines += [f'- **{field}**: {display}']
                    lines += ['']
            unresolved = json.loads(origin.get('unresolved_json', '[]'))
            if unresolved:
                lines += ['**연결 미확정 — 원문 밖의 참조를 추측하지 않았습니다.**', '', '```json', json.dumps(unresolved, ensure_ascii=False, indent=2), '```', '']
        (output/'records.md').write_text('\n'.join(lines).rstrip()+'\n')
        counts = dict(collections.Counter(r['kind'] for r in entries))
        c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    result = {'goal':GOAL, 'project':PROJECT, 'source_files':[{ 'name':Path(p).name, 'sha256':sha} for p,_,sha in docs],
              'scope':'Four previously published excerpts only; no live database or other goals.',
              'counts':counts, 'migration':imported, 'repair':report,
              'validation':{'core_records_read':len(entries), 'original_bytes_preserved':True, 'foreign_keys':'PASS', 'integrity':'PASS', 'fresh_approvals':0, 'executions':0, 'fresh_evidence':0},
              'db_sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
    (output/'migration.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'counts':counts, 'unresolved_links':len(report['unresolved_links'])}, ensure_ascii=False))

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    build(parser.parse_args().output)
