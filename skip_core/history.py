"""DB-only historical read model. Original bytes never become current approvals."""
import json
from .errors import require


def summaries(core,goal=None,limit=30,offset=0,search=None):
    condition="project_id=? AND NOT EXISTS(SELECT 1 FROM document_dispositions dd WHERE dd.project_id=imported_documents.project_id AND dd.document_id=imported_documents.id AND dd.disposition IN ('converted','excluded'))";args=[core.project]
    if goal:condition+=' AND goal_id=?';args.append(goal)
    if search:
        require(isinstance(search,str) and len(search)<=160,'INVALID_INPUT','Invalid history search')
        condition+=' AND (title LIKE ? OR body_text LIKE ?)';args.extend(['%'+search+'%']*2)
    rows=core.c.execute('SELECT id,goal_id,source_path,kind,title,historical_status,length(content) AS bytes FROM imported_documents WHERE '+condition+' ORDER BY source_path LIMIT ? OFFSET ?',(*args,limit,offset))
    return [dict(r,verification='historical_unverified',authority=False) for r in rows]


def read(core,p):
    row=core.c.execute('SELECT id,goal_id,source_path,kind,title,historical_status,content_sha256,length(content) AS bytes,body_text,metadata_json FROM imported_documents WHERE project_id=? AND id=?',(core.project,p['id'])).fetchone()
    require(row is not None,'NOT_FOUND','Historical record unavailable')
    start=p.get('offset',0);limit=p.get('length',16000)
    require(type(start) is int and start>=0 and type(limit) is int and 1<=limit<=32000,'INVALID_INPUT','Invalid history page')
    result=dict(row);body=result.pop('body_text');meta=json.loads(result.pop('metadata_json'))
    result.update(body=body[start:start+limit] if body is not None else None,offset=start,next_offset=start+limit if body and start+limit<len(body) else None,
                  metadata=meta,verification='historical_unverified',authority=False)
    result['links']=[dict(r) for r in core.c.execute('SELECT label,target_text,target_document_id,resolution FROM imported_links WHERE project_id=? AND document_id=? ORDER BY ordinal LIMIT 100',(core.project,p['id']))]
    result['record_refs']=[dict(r) for r in core.c.execute('SELECT requirement_id,requirement_revision,plan_id,plan_revision,work_item_id,work_revision FROM imported_record_refs WHERE project_id=? AND document_id=? ORDER BY ordinal LIMIT 100',(core.project,p['id']))]
    return result
