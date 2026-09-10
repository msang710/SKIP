"""One native read path for records, irrespective of their original storage format."""
import json
from . import records
from .errors import require

def origin(c,p,kind,ident,rev):
    row=c.execute('SELECT o.*,d.source_path FROM record_origins o JOIN imported_documents d ON d.project_id=o.project_id AND d.id=o.document_id WHERE o.project_id=? AND o.kind=? AND o.record_id=? AND o.revision=?',(p,kind,ident,rev)).fetchone()
    return dict(row) if row else None

def settled(record):
    o=record.get('origin')
    return bool(o and o['source_status'].strip().lower() in ('confirmed','approved','accepted','확정','승인'))

def listing(core,goal,kind,limit,offset,search=None):
    require(kind is None or kind in (*records.FIELDS,'evidence'),'INVALID_INPUT','Unknown record kind')
    unions=[];args=[]
    for k in (*records.FIELDS,'evidence'):
        if k=='goal' or (kind and k!=kind):continue
        if k=='evidence':
            sql="SELECT e.id,1 revision,'evidence' kind,sc.goal_id,substr(e.summary,1,120) title,'active' lifecycle FROM evidence e JOIN snapshots s ON s.project_id=e.project_id AND s.id=e.snapshot_id JOIN scopes sc ON sc.project_id=s.project_id AND sc.id=s.scope_id WHERE e.project_id=? AND e.sealed_at IS NOT NULL"
            if goal:sql+=' AND sc.goal_id=?'
        else:
            title='question' if k=='decision' else 'title'
            sql=f"SELECT h.id,v.revision,'{k}' kind,h.goal_id,substr(v.{title},1,240) title,h.lifecycle FROM {k}s h JOIN {k}_versions v ON v.project_id=h.project_id AND v.id=h.id AND v.revision=h.current_revision WHERE h.project_id=? AND h.lifecycle<>'archived'"
            if goal:sql+=' AND h.goal_id=?'
        args.append(core.project)
        if goal:args.append(goal)
        unions.append(sql)
    sql='SELECT * FROM ('+' UNION ALL '.join(unions)+')'
    if search:
        require(isinstance(search,str) and len(search)<=160,'INVALID_INPUT','Invalid search')
        sql+=' WHERE title LIKE ?';args.append('%'+search+'%')
    sql+=' ORDER BY kind,title,id LIMIT ? OFFSET ?';args.extend([limit,offset])
    rows=[]
    for row in core.c.execute(sql,args):
        r=dict(row);r['origin']=origin(core.c,core.project,r['kind'],r['id'],r['revision'])
        if r['origin']:r['origin'].pop('source_excerpt',None)
        if r['kind']=='decision':
            from .decision_state import attach
            detail=attach(core,records.get(core.c,core.project,'decision',r['id'],r['revision']))
            for key in ('selection_state','selection_stale','action_state'):
                r[key]=detail[key]
            option=detail['selected_option']
            r['selected_option']={key:option[key] for key in ('option_id','label')} if option else None
        rows.append(r)
    return rows

def evidence_record(core,p):
    row=core.c.execute('SELECT * FROM evidence WHERE project_id=? AND id=? AND sealed_at IS NOT NULL',(core.project,p['id'])).fetchone()
    require(row is not None,'NOT_FOUND','Evidence unavailable')
    result=dict(row)
    return {'kind':'evidence','id':row['id'],'revision':1,'fields':{k:result[k] for k in ('summary','method','surface','result','provenance','observed_at')},'children':{},'origin':origin(core.c,core.project,'evidence',row['id'],1),'lifecycle':'active'}
