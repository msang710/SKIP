"""Offline maintenance only. No legacy reader or importer is exposed at runtime.

Every source byte is retained in SQLite. Historical claims and structured text
are queryable; no imported approval, PASS claim or task grants current authority.
"""
import argparse
import hashlib
import json
import mimetypes
from pathlib import Path,PurePosixPath
import posixpath
import re
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import yaml
from skip_core.db import Database
from skip_core.authority import Principal
from skip_core.service import Core
from skip_core.common import digest,encoded,now
from skip_core import records
from skip_core.errors import require

REQUEST='배포하고 내 프로젝트 기록들 마이그레이션해'
TEXT_TYPES={'.md','.yaml','.yml','.json','.py','.sql','.log','.txt','.toml','.csv'}

def inventory(root):
    root=Path(root).resolve(strict=True);rows=[];excluded=[]
    for path in sorted((root/'projects').rglob('*')):
        rel=path.relative_to(root)
        if '.git' in rel.parts:
            if path.is_file():excluded.append(rel.as_posix())
            continue
        require(not path.is_symlink(),'INVALID_INPUT','Source symlink requires explicit resolution: '+str(rel))
        if not path.is_file():continue
        blob=path.read_bytes()
        require(len(blob)<=16*1024*1024,'INVALID_INPUT','Source exceeds migration size bound')
        rows.append({'path':rel.as_posix(),'size':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
    return {'files':rows,'excluded_git_files':excluded,'digest':digest(rows)}

def parse(blob,path):
    try:value=blob.decode('utf-8-sig')
    except UnicodeDecodeError:return {},None
    if Path(path).suffix.lower() not in TEXT_TYPES:return {},None
    meta={};body=value
    if value.startswith('---\n'):
        parts=value.split('\n---',1)
        if len(parts)==2:
            try:
                loaded=yaml.safe_load(parts[0][4:]);meta=loaded if isinstance(loaded,dict) else {}
            except yaml.YAMLError:meta={'migration_warning':'unparsed frontmatter; original retained'}
            body=parts[1].lstrip('\r\n')
    elif path.endswith(('.yaml','.yml')):
        try:
            loaded=yaml.safe_load(value);meta=loaded if isinstance(loaded,dict) else {}
        except yaml.YAMLError:meta={'migration_warning':'unparsed YAML; original retained'}
    return json.loads(json.dumps(meta,ensure_ascii=False,default=str)),body

def kind(path):
    p=PurePosixPath(path);name=p.stem.lower()
    if 'NOW' in p.parts:return 'current_snapshot'
    if p.suffix=='.md':
        if 'prd' in name or 'user_stor' in name or 'requirement' in name:return 'requirement'
        if 'design' in name or name in ('db_schema','data_dictionary','implementation_plan','implementation_spec'):return 'plan'
        if 'task' in name:return 'work_item'
        if 'impact' in name:return 'investigation'
        return 'record'
    return 'attachment'

def goal_for(path):
    p=PurePosixPath(path)
    if len(p.parts)>=3 and p.parts[0]=='features':return p.parts[1]
    if len(p.parts)>=3 and p.parts[:2]==('NOW','goals'):return p.stem
    return None

def sections(body):
    lines=body.splitlines(keepends=True);out=[];start=0;heading='본문';fence=None
    for i,line in enumerate(lines):
        m=re.match(r'^\s*(`{3,}|~{3,})',line)
        if m:
            marker=m[1][0]
            if fence is None:fence=marker
            elif fence==marker:fence=None
        h=re.match(r'^#{1,6}\s+(.+?)\s*#*\s*$',line) if fence is None else None
        if h:
            if i>start:out.append((heading,''.join(lines[start:i]),start+1,i))
            start=i;heading=h[1]
    if start<len(lines):out.append((heading,''.join(lines[start:]),start+1,len(lines)))
    return out

def section_kind(heading):
    for pattern,k in [('결정|decision','decision'),('요구|requirement|기준|criteria','requirement'),('설계|design','plan'),('작업|task','work_item'),('검증|validation|확인|evidence','evidence'),('근거|rationale|이유','rationale')]:
        if re.search(pattern,heading,re.I):return k
    return 'prose'

def migrate(root,target,manifest,registry=None):
    root=Path(root).resolve();target=Path(target)
    require(not target.exists(),'CONFLICT','Migration writes a new candidate only')
    require(inventory(root)['digest']==manifest['digest'],'STALE','Source inventory changed')
    imported=[];batch='migration-'+manifest['digest'][:24];timestamp=now()
    registry=registry or {};project_settings=registry.get('projects',{})
    with Database(target,create=True) as db:
        c=db.connection;core=Core(db)
        with db.transaction():
            records.insert(c,'record_imports',dict(id=batch,inventory_digest=manifest['digest'],file_count=len(manifest['files']),request_text=REQUEST,created_at=timestamp))
            for project in sorted({PurePosixPath(v['path']).parts[1] for v in manifest['files']}):
                rows=[v for v in manifest['files'] if PurePosixPath(v['path']).parts[1]==project]
                project_meta={}
                descriptor=root/'projects'/project/'project.yaml'
                if descriptor.is_file():project_meta,_=parse(descriptor.read_bytes(),'project.yaml')
                records.insert(c,'projects',dict(id=project,name=str(project_meta.get('display_name') or project),state='active',created_at=timestamp))
                source_defs={'main':{'kind':'directory','source_root':'.'},**project_meta.get('sources',{})}
                for sid,source in source_defs.items():
                    relative=str(source.get('source_root') or '.')
                    if PurePosixPath(relative).is_absolute() or '..' in PurePosixPath(relative).parts:relative='.'
                    records.insert(c,'sources',dict(project_id=project,id=sid,name=sid,kind='directory',logical_path=relative,created_at=timestamp))
                    configured=project_settings.get(project,{}).get('sources',{}).get(sid,{})
                    identities=source.get('repository',{}).get('identities',[])+([configured['repository_identity']] if configured.get('repository_identity') else [])
                    for identity in set(identities):
                        c.execute('INSERT OR IGNORE INTO project_identities VALUES(?,?,?)',(project,identity,configured.get('source_root',relative)))
                core.project=project;core.principal=Principal(project,batch,kind='human',method='host_user_turn',verifier='current-user-authorized-offline-migration',event_key=batch,user_text=REQUEST)
                core.context=None;core.key=digest([batch,project]);core.counter=0;core.command={'command':'maintenance.migrate'}
                core.interaction=core._interaction(core.principal,core.command);core.event=core.event_record('maintenance.migrate')
                request=core.new_request(REQUEST,'investigate')
                goals=sorted({g for row in rows if (g:=goal_for('/'.join(PurePosixPath(row['path']).parts[2:])))})
                for goal in goals:
                    event=core.event_record('history.goal_imported')
                    title=goal
                    for candidate in [root/'projects'/project/'features'/goal/'prd.md',root/'projects'/project/'NOW/goals'/(goal+'.md')]:
                        if candidate.is_file():
                            metadata,_=parse(candidate.read_bytes(),candidate.name)
                            if metadata.get('title'):title=str(metadata['title']);break
                    payload={'kind':'goal','id':goal,'request_id':request,'expected_revision':0,'fields':{'title':title,
                        'intent':'기존 기록에서 이관한 작업: '+goal,'success_definition':'기존 기록의 목표·결정·검증을 확인하고 현재 요청에 맞춰 계속한다. 이관 자체는 실행 승인이 아니다.'}}
                    ident,rev=records.publish(c,project,payload,event,allow_new_goal=True)
                    records.advance(c,project,'goal',ident,rev,core.event_record('history.goal_available'))
                    records.insert(c,'request_goals',dict(project_id=project,request_id=request,goal_id=goal))
                doc_ids={};doc_values=[];goal_refs={}
                for row in rows:
                    path='/'.join(PurePosixPath(row['path']).parts[2:]);blob=(root/row['path']).read_bytes()
                    require(hashlib.sha256(blob).hexdigest()==row['sha256'],'STALE','Source changed during import')
                    meta,body=parse(blob,path);g=goal_for(path);k=kind(path);ident='doc-'+digest(path)[:28]
                    title=str(meta.get('title') or next((h for h,_,_,_ in sections(body or '') if h!='본문'),PurePosixPath(path).stem))
                    records.insert(c,'imported_documents',dict(project_id=project,id=ident,import_id=batch,goal_id=g,source_path=path,kind=k,title=title,
                        content=blob,content_sha256=row['sha256'],body_text=body,metadata_json=encoded(meta),historical_status=str(meta.get('status') or 'UNSPECIFIED'),created_at=timestamp))
                    doc_ids[path]=ident;doc_values.append((ident,path,body))
                    for ordinal,(heading,part,start,end) in enumerate(sections(body or '')):
                        records.insert(c,'imported_sections',dict(project_id=project,document_id=ident,ordinal=ordinal,heading=heading,kind=section_kind(heading) if section_kind(heading)!='prose' else k,body=part,start_line=start,end_line=end))
                    if g and body and k in ('requirement','plan'):
                        # Split only oversized prose, retaining exact complete original separately.
                        chunks=[body[i:i+60000] for i in range(0,len(body),60000)]
                        for ordinal,chunk in enumerate(chunks):
                            rid='import-'+digest([path,ordinal])[:28]
                            fields=({'title':title,'statement':chunk,'rationale':'기존 문서 원문. 출처: '+path} if k=='requirement' else
                              {'title':title,'design_body':chunk,'scope_description':'기존 문서의 범위와 제약을 보존한다.','alternatives_body':'원문 본문 참조.','rollback_body':'원문 본문 참조. 현재 실행 전 재확인 필요.'} if k=='plan' else
                              {'operation':'implement','title':title,'instruction_body':chunk,'completion_definition':'원문 검증 항목을 현재 소스와 연결해 다시 확인한다.','workflow_depth':'investigate','request_id':request})
                            children={'checks':[{'check_id':'revalidate-import','description':'이관된 계획과 현재 소스·제품 결정을 연결해 실행 전 검토','surface':'source','required':1}]} if k=='work_item' else {'criteria':[{'criterion_id':'historical-review','description':'원문 요구사항과 검증 항목 확인','given_text':'이관된 원문','when_text':'현재 요청으로 계속하기 전','then_text':'원문 기준을 현재 소스와 연결해 확인','required':1}]} if k=='requirement' else {'items':[{'item_id':'original','title':title,'design_body':chunk,'verification_body':'원문 검증 항목을 현재 소스에서 재확인. 이관은 검증이 아님.','position':0}]}
                            payload={'kind':k,'id':rid,'request_id':request,'goal_id':g,'expected_revision':0,'fields':fields,'children':children}
                            rid,revision=records.publish(c,project,payload,core.event_record('history.text_imported'))
                            records.advance(c,project,k,rid,revision,core.event_record('history.text_available'))
                            event=core.event_record('history.hold_until_review')
                            c.execute(f'UPDATE {k}s SET lifecycle=?,state_version=state_version+1,last_event_id=? WHERE project_id=? AND id=?',('held',event,project,rid))
                            ref={'project_id':project,'document_id':ident,'ordinal':ordinal,k+'_id':rid,('work_revision' if k=='work_item' else k+'_revision'):revision}
                            records.insert(c,'imported_record_refs',ref)
                            goal_refs.setdefault(g,[]).append({'kind':k,'id':rid,'revision':revision})
                for ident,path,body in doc_values:
                    for ordinal,match in enumerate(re.finditer(r'\[([^\]\n]*)\]\(([^\)\n]+)\)',body or '')):
                        label,target_text=match.groups();raw=target_text.strip().strip('<>').split('#',1)[0]
                        external=bool(re.match(r'^[a-zA-Z][\w+.-]*:|^/',raw))
                        target_path=posixpath.normpath(posixpath.join(posixpath.dirname(path),raw)) if raw else path
                        target_doc=doc_ids.get(target_path) if not external else None
                        records.insert(c,'imported_links',dict(project_id=project,document_id=ident,ordinal=ordinal,label=label,target_text=target_text,target_document_id=target_doc,resolution='external' if external else 'resolved' if target_doc else 'unresolved'))
                imported.append({'project_id':project,'files':len(rows),'goals':len(goals),'structured_records':sum(len(v) for v in goal_refs.values())})
            require(not c.execute('PRAGMA foreign_key_check').fetchall(),'RECOVERY_REQUIRED','Imported relation check failed')
            require(inventory(root)['digest']==manifest['digest'],'STALE','Source changed before commit')
        require(c.execute('PRAGMA integrity_check').fetchone()[0]=='ok','RECOVERY_REQUIRED','Imported DB integrity failed')
        for row in manifest['files']:
            parts=PurePosixPath(row['path']).parts;data=c.execute('SELECT content FROM imported_documents WHERE project_id=? AND source_path=?',(parts[1],'/'.join(parts[2:]))).fetchone()[0]
            require(hashlib.sha256(data).hexdigest()==row['sha256'],'RECOVERY_REQUIRED','Content verification failed')
        c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    return {'status':'VERIFIED','inventory_digest':manifest['digest'],'files':len(manifest['files']),'excluded_git_files':len(manifest['excluded_git_files']),
            'projects':imported,'source_hashes_verified':True,'fresh_approvals':0,'fresh_evidence_passes':0,'executions':0}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--candidate',type=Path);p.add_argument('--registry',type=Path);p.add_argument('--report',type=Path,required=True)
    a=p.parse_args();manifest=inventory(a.root)
    result=migrate(a.root,a.candidate,manifest,yaml.safe_load(a.registry.read_text()) if a.registry else None) if a.candidate else manifest
    a.report.parent.mkdir(parents=True,exist_ok=True);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
