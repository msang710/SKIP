"""Shared bounded read models for CLI, MCP and native UIs."""
import json
from . import records
from .decision_state import attach as attach_selection
from .common import encoded
from .errors import CoreError, require
from .execution import verify_snapshot


def query_core(core, query, p, principal, context):
    allowed = {
        'entry.inspect': {'request_id'}, 'stage.assess': {'request_id','goal_id'},
        'request.list': {'goal_id','cursor','limit'}, 'request': {'id'},
        'status': {'goal_id','cursor','limit'}, 'inbox': {'goal_id','cursor','limit'},
        'context': {'goal_id','stage','budget','snapshot_id','work_id','request_id'}, 'record': {'kind','id','revision'},
        'trace': {'kind','id','revision'}, 'execution.status': {'execution_id'},
        'failure.history': {'id','limit','cursor'}, 'learning.list': {'kind','goal_id','limit','cursor'}, 'learning.record': {'kind','id','revision'}, 'guidance': {'goal_id','snapshot_id','work_id'}, 'assurance': {'claim_id','snapshot_id'},
        'changes': {'since','limit'}, 'settings': set(), 'risks': {'goal_id'},
        'record.list': {'goal_id','cursor','limit','kind','search'},
        'history': {'goal_id','cursor','limit','search'}, 'history.record': {'id','offset','length'},
    }
    require(query in allowed and isinstance(p,dict) and set(p)<=allowed[query],'INVALID_INPUT','Invalid query')
    core.project,core.principal,core.context=principal.project_id,principal,context
    connection_problem = None
    if context:
        require(context.project_id==principal.project_id,'PROJECT_MISMATCH','Context project mismatch')
        try:
            context.check()
        except CoreError as exc:
            if query != 'execution.status' or exc.code not in ('STALE', 'CONTEXT_EXPIRED'):
                raise
            connection_problem = 'target_changed' if exc.code == 'STALE' else 'revalidation_required'
    project=core.c.execute('SELECT * FROM projects WHERE id=?',(core.project,)).fetchone()
    require(project is not None,'NOT_INITIALIZED','Connect this project first')
    sequence=core.c.execute('SELECT COALESCE(max(sequence),0) FROM events WHERE project_id=?',(core.project,)).fetchone()[0]
    result={'schema':'skip-core/v1','status':'ok','project_id':core.project,'sequence':sequence,'enforcement':'advisory'}
    if query=='changes':
        since=p.get('since',sequence);bound=p.get('limit',100)
        require(type(since) is int and 0<=since<=sequence and type(bound) is int and 1<=bound<=100,'INVALID_INPUT','Invalid change window')
        events=[dict(r) for r in core.c.execute('SELECT e.id,e.sequence,e.kind FROM events e JOIN command_receipts r ON r.project_id=e.project_id AND r.event_id=e.id WHERE e.project_id=? AND e.sequence>? ORDER BY e.sequence LIMIT ?',(core.project,since,bound+1))]
        complete=len(events)<=bound;events=events[:bound]
        # Versions and event grouping are read in the same transaction as the watermark.
        for event in events:
            event['records']=[]
            for kind in records.FIELDS:
                event['records'] += [dict(r,kind=kind) for r in core.c.execute(
                    f'SELECT id,revision FROM {kind}_versions WHERE project_id=? AND created_event_id=?',(core.project,event['id']))]
        return {**result,'data':{'sequence':sequence,'events':events,'complete':complete,'resync_required':not complete or (since<sequence and not events)}}
    freshness_cache={}
    def freshness(snap):
        if snap not in freshness_cache:
            try:
                verify_snapshot(core,snap)
                freshness_cache[snap]='current'
            except CoreError as exc:
                freshness_cache[snap]='stale' if exc.code=='STALE' else 'unverified'
            except OSError:
                freshness_cache[snap]='unverified'
        return freshness_cache[snap]
    def heads(kind,goal=None,limit=100,offset=0):
        where="project_id=? AND lifecycle<>'archived'"; args=[core.project]
        if query=='inbox' and kind=='decision':
            where+=" AND NOT EXISTS(SELECT 1 FROM record_origins o WHERE o.project_id=decisions.project_id AND o.kind='decision' AND o.record_id=decisions.id AND o.revision=decisions.current_revision AND lower(o.source_status) IN ('confirmed','approved','accepted','확정','승인'))"
        if goal:
            where+=' AND '+('id' if kind=='goal' else 'goal_id')+'=?'; args.append(goal)
        # Mutation sequence orders revisions and lifecycle changes, never reads.
        order = ('(SELECT e.sequence FROM events e WHERE e.project_id=goals.project_id '
                 'AND e.id=goals.last_event_id) DESC, id DESC') if kind=='goal' else 'created_at,id'
        return [records.get(core.c,core.project,kind,r['id']) for r in core.c.execute(
            f'SELECT id FROM {kind}s WHERE {where} AND current_revision IS NOT NULL ORDER BY {order} LIMIT ? OFFSET ?',(*args,limit,offset))]
    limit=p.get('limit',30)
    require(type(limit) is int and 1<=limit<=100,'INVALID_INPUT','Invalid page size')
    offset=0
    if p.get('cursor'):
        try:
            seq,offset=map(int,p['cursor'].split(':'))
        except (ValueError,AttributeError):
            raise CoreError('INVALID_INPUT','Invalid cursor')
        require(seq==sequence and 0<=offset<=100000,'STALE','List changed; refresh from the first page')
    goal=p.get('goal_id')
    if goal:
        records.get(core.c,core.project,'goal',goal)
    from .history import summaries,read as read_history
    if query in ('entry.inspect','stage.assess'):
        from .entry_runtime import inspect,assess
        result['data']=(inspect if query=='entry.inspect' else assess)(core,p)
        return result
    if query=='failure.history':
        from .learning import get
        get(core,'failure',p['id'])
        rows=[dict(r) for r in core.c.execute("SELECT 'occurrence' kind,id,evidence_id,classification detail,created_at FROM failure_occurrences WHERE project_id=? AND case_id=? UNION ALL SELECT 'attempt',id,evidence_id,action_body,created_at FROM failure_attempts WHERE project_id=? AND case_id=? ORDER BY created_at DESC,id LIMIT ? OFFSET ?",(core.project,p['id'],core.project,p['id'],limit+1,offset))]
        result['data']={'items':rows[:limit],'next_cursor':f'{sequence}:{offset+limit}' if len(rows)>limit else None}
    elif query=='learning.list':
        from .learning import listing
        rows=listing(core,p['kind'],goal,limit+1,offset)
        result['data']={'items':rows[:limit],'next_cursor':f'{sequence}:{offset+limit}' if len(rows)>limit else None}
    elif query=='learning.record':
        from .learning import get
        result['data']=get(core,p['kind'],p['id'],p.get('revision'))
    elif query=='guidance':
        from .guidance import projection
        require(goal is not None,'INVALID_INPUT','Select a goal')
        result['data']=projection(core,goal,p.get('snapshot_id'),p.get('work_id'))
    elif query=='assurance':
        from .assurance import evaluate
        result['data']=evaluate(core,p['claim_id'],p['snapshot_id'])
    elif query in ('request.list','request'):
        args=[core.project]
        where='r.project_id=?'
        if goal:
            where+=' AND EXISTS(SELECT 1 FROM request_goals g WHERE g.project_id=r.project_id AND g.request_id=r.id AND g.goal_id=?)';args.append(goal)
        if query=='request':
            require(isinstance(p.get('id'),str),'INVALID_INPUT','Request ID required')
            where+=' AND r.id=?';args.append(p['id'])
        projection='r.intent' if query=='request' else 'substr(r.intent,1,240) intent'
        rows=[dict(r) for r in core.c.execute(f'SELECT r.id,{projection},r.operation,r.created_at FROM requests r WHERE {where} ORDER BY r.created_at DESC,r.id DESC LIMIT ? OFFSET ?',(*args,1 if query=='request' else limit+1,0 if query=='request' else offset))]
        for row in rows:
            row['goals']=[dict(g) for g in core.c.execute('SELECT g.id,v.title FROM request_goals l JOIN goals g ON g.project_id=l.project_id AND g.id=l.goal_id JOIN goal_versions v ON v.project_id=g.project_id AND v.id=g.id AND v.revision=g.current_revision WHERE l.project_id=? AND l.request_id=? ORDER BY g.id',(core.project,row['id']))]
            row['authority']='Stored request is context, not permission to start or deploy'
        if query=='request':
            require(rows,'NOT_FOUND','Request is unavailable in this project')
            result['data']=rows[0]
        else:result['data']={'items':rows[:limit],'next_cursor':f'{sequence}:{offset+limit}' if len(rows)>limit else None}
    elif query=='record.list':
        from .record_views import listing
        rows=listing(core,goal,p.get('kind'),limit+1,offset,p.get('search'))
        result['data']={'items':rows[:limit],'next_cursor':f'{sequence}:{offset+limit}' if len(rows)>limit else None}
    elif query=='history':
        rows=summaries(core,goal,limit+1,offset,p.get('search'))
        result['data']={'items':rows[:limit],'next_cursor':f'{sequence}:{offset+limit}' if len(rows)>limit else None}
    elif query=='history.record':
        result['data']=read_history(core,p)
    elif query=='settings':
        result['data']={'settings':[dict(r,body=json.loads(r['validated_body_json'])) for r in core.current_settings()]}
    elif query=='risks':
        require(goal is not None,'INVALID_INPUT','Select a goal')
        rows=core.c.execute('SELECT * FROM risk_assessments WHERE project_id=? AND goal_id=? AND sealed_at IS NOT NULL ORDER BY created_at DESC,id LIMIT 32',
                            (core.project,goal)).fetchall()
        result['data']={'assessments':[dict(r,freshness=freshness(r['snapshot_id'])) for r in rows]}
    elif query in ('record','trace'):
        require({'kind','id'}<=set(p),'INVALID_INPUT','Record identity required')
        from .record_views import evidence_record
        r=evidence_record(core,p) if p['kind']=='evidence' else records.get(core.c,core.project,p['kind'],p['id'],p.get('revision'))
        require(len(encoded(r).encode())<=512000,'INVALID_INPUT','Record exceeds response budget')
        if p['kind']=='decision': attach_selection(core,r)
        result['data']=r
    elif query=='execution.status':
        x=core.one('executions',p['execution_id'])
        d=core.c.execute('SELECT state,attempt_count,last_error FROM deliveries WHERE project_id=? AND execution_id=?',(core.project,x['id'])).fetchone()
        # No DB receipt digest becomes a route, token or reconstructed target.
        result['data']={k:x[k] for k in ('id','work_item_id','work_revision','state','state_version','started_at','finished_at')}
        result['data']['delivery']=dict(d)
        current = bool(context and not connection_problem and x['dispatch_context_digest']==context.fingerprint)
        state = connection_problem or ('current' if current else
            'revalidation_required' if context and context.caller_verified else 'unverified')
        result['data']['connection_current'] = current  # compatibility; not caller identity
        result['data']['connection'] = {'state':state, 'execution_authority_restored':False}

        result['data']['validation_complete']=False
    elif query=='inbox':
        items=heads('decision',goal,limit+1,offset)
        from .record_views import settled
        items=[item for item in items if not settled(item)]
        for item in items: attach_selection(core,item)
        result['data']={'items':items[:limit],'next_cursor':f'{sequence}:{offset+limit}' if len(items)>limit else None}
    elif query=='context':
        require(goal and p.get('stage') in ('impact','requirements','design','tasks','implementation','validation','restore'),
                'INVALID_INPUT','Select a goal and stage')
        budget=p.get('budget',18000)
        require(type(budget) is int and 1024<=budget<=128000,'INVALID_INPUT','Invalid context budget')
        stage=p['stage']; kinds=['goal','decision']
        if stage in ('design','tasks','implementation','validation','restore'): kinds+=['requirement','plan']
        if stage in ('tasks','implementation','validation','restore'): kinds+=['work_item']
        data={'goal_id':goal,'stage':stage,'records':[],'required_expansions':[],'complete':True}
        for kind in kinds:
            rows=heads(kind,goal,129)
            if len(rows)>128:
                data['complete']=False;data['required_expansions'].append({'kind':kind,'reason':'record_limit'})
            for r in rows[:128]:
                if kind=='decision': attach_selection(core,r)
                if len(encoded(data).encode())+len(encoded(r).encode())+512>budget:
                    data['complete']=False
                    if len(data['required_expansions'])<32:
                        data['required_expansions'].append({'kind':kind,'id':r['id'],'revision':r['revision']})
                else: data['records'].append(r)
        from .policy import effective
        data['policy']=effective(core,'implement' if stage=='implementation' else 'plan' if stage in ('requirements','design','tasks') else 'investigate')
        historical=summaries(core,goal,33)
        if historical:
            data['historical_records']=historical[:32]
            data['complete']=False
            data['required_expansions'].append({'kind':'history','goal_id':goal,'reason':'Read original decisions and constraints before continuing; history is not new authority','more':len(historical)>32})
        from .record_views import origin
        data['observations']=[dict(r,origin=origin(core.c,core.project,'evidence',r['id'],1),freshness=freshness(r['snapshot_id'])) for r in core.c.execute("SELECT e.id,e.result,e.snapshot_id,substr(e.summary,1,800) summary,e.observed_at FROM evidence e JOIN snapshots s ON s.project_id=e.project_id AND s.id=e.snapshot_id JOIN scopes sc ON sc.project_id=s.project_id AND sc.id=s.scope_id WHERE e.project_id=? AND sc.goal_id=? ORDER BY e.created_at DESC,e.id LIMIT 8",(core.project,goal))]
        if data['observations']:data['required_expansions'].append({'kind':'evidence','goal_id':goal,'reason':'Observation summaries; read exact records for full scope'})
        from .guidance import projection
        from .learning import listing
        data['failure_guidance']=projection(core,goal,p.get('snapshot_id'),p.get('work_id'))
        data['assurance']={'claims':listing(core,'claim',goal,31),'notice':'Read each claim against current scope evidence before making an assurance statement.'}
        if len(data['assurance']['claims'])>30:
            data['assurance']['claims']=data['assurance']['claims'][:30];data['complete']=False
            data['required_expansions'].append({'kind':'claim','query':'learning.list','reason':'record_limit'})
        if not data['failure_guidance']['complete']:
            data['complete']=False;data['required_expansions'].append({'kind':'guideline','query':'learning.list','reason':'lookup_limit'})
        if p.get('request_id'):
            from .entry_runtime import inspect,assess
            data['stage_assessment']=assess(core,{'request_id':p['request_id'],'goal_id':goal})
            data['entry_basis']=inspect(core,{'request_id':p['request_id']})
        if p.get('request_id'):
            data['authoring_base']={'goal_id':goal,'request_id':p['request_id']}
        data['authority']='Context is reading material, not execution permission'
        while len(encoded({**result,'data':data}).encode()) > budget:
            data['complete']=False
            if 'entry_basis' in data:
                data.pop('entry_basis');data.pop('stage_assessment',None)
                data['required_expansions'].append({'query':'entry.inspect','request_id':p['request_id'],'reason':'budget'})
            elif data.get('failure_guidance',{}).get('items'):
                removed=data['failure_guidance']['items'].pop();data['failure_guidance']['complete']=False
                data['required_expansions'].append({'kind':'guideline','id':removed['id'],'revision':removed['revision'],'query':'learning.record'})
            elif data.get('assurance',{}).get('claims'):
                removed=data['assurance']['claims'].pop();data['required_expansions'].append({'kind':'claim','id':removed['id'],'revision':removed['revision'],'query':'learning.record'})
            elif data['records']:
                removed=data['records'].pop()
                data['required_expansions'].append({'kind':removed['kind'],'id':removed['id'],'revision':removed['revision']})
            elif data.get('observations'):
                removed=data['observations'].pop();data['required_expansions'].append({'kind':'evidence','id':removed['id'],'revision':1})
            elif data.get('historical_records'):
                data['historical_records'].pop();data['historical_list_truncated']=True
            elif 'policy' in data:
                data.pop('policy');data['required_expansions'].append({'kind':'policy','reason':'budget'})
            elif data['required_expansions']:
                data['required_expansions'].pop();data['expansion_list_truncated']=True
            else:break
        result['data']=data
    else:
        goals=heads('goal',goal,limit+1,offset)
        where='f.project_id=?';args=[core.project]
        if goal: where+=' AND f.goal_id=?';args.append(goal)
        from .record_views import origin
        facts=[dict(r) for r in core.c.execute('SELECT f.*,e.provenance FROM now_facts f JOIN evidence e ON e.project_id=f.project_id AND e.id=f.evidence_id '
            f'WHERE {where} ORDER BY f.created_at DESC LIMIT 30',args)]
        for f in facts:
            f['freshness']=freshness(f['snapshot_id'])
            f['statement']=f['statement'][:4000]
            f['details_record']={'kind':'evidence','id':f['evidence_id']}
            from .record_views import origin
            f['origin']=origin(core.c,core.project,'evidence',f['evidence_id'],1)
        checks=[dict(r) for r in core.c.execute('SELECT e.id,e.summary,e.surface,e.result,e.provenance,e.snapshot_id FROM evidence e '
            'JOIN snapshots s ON s.project_id=e.project_id AND s.id=e.snapshot_id JOIN scopes sc ON sc.project_id=s.project_id AND sc.id=s.scope_id '
            "WHERE e.project_id=? AND (? IS NULL OR sc.goal_id=?) AND e.sealed_at IS NOT NULL AND NOT EXISTS(SELECT 1 FROM record_origins o WHERE o.project_id=e.project_id AND o.kind='evidence' AND o.record_id=e.id AND o.classification<>'current_snapshot') ORDER BY e.created_at DESC,e.id LIMIT 30",
            (core.project,goal,goal))]
        for check in checks:
            check['freshness']=freshness(check['snapshot_id'])
            check['summary']=check['summary'][:1500]
            check['origin']=origin(core.c,core.project,'evidence',check['id'],1)
        works=heads('work_item',goal,101)
        works_truncated=len(works)>100
        works=works[:100]
        remaining=[]
        for work in works:
            if work.get('origin'):
                if work['origin']['source_status'].strip().lower() in ('completed','done','complete','완료'):continue
                remaining.append({'work_id':work['id'],'check_id':'recorded-state','description':work['fields']['title'],'state':work['origin']['source_status']})
                continue
            for check in work['children']['checks']:
                if not check['required']:continue
                row=core.c.execute('SELECT r.verdict,e.snapshot_id FROM work_check_results r JOIN evidence e ON e.project_id=r.project_id AND e.id=r.evidence_id '
                    'WHERE r.project_id=? AND r.work_item_id=? AND r.work_revision=? AND r.check_id=? ORDER BY (SELECT sequence FROM events ev WHERE ev.project_id=e.project_id AND ev.id=e.event_id) DESC LIMIT 1',
                    (core.project,work['id'],work['revision'],check['check_id'])).fetchone()
                if not row or row['verdict']!='PASS' or freshness(row['snapshot_id'])!='current':
                    remaining.append({'work_id':work['id'],'check_id':check['check_id'],'description':check['description'],
                                      'state':('STALE' if row['verdict']=='PASS' and freshness(row['snapshot_id'])=='stale' else 'EVIDENCE_PENDING' if row['verdict']=='PASS' else row['verdict']) if row else 'NOT_RUN'})
        for work in works:
            work['fields']={k:v for k,v in work['fields'].items() if k in ('title','operation','workflow_depth')}
            work['details_omitted']=True
        result['data']={'historical_records':summaries(core,goal,30),'goals':goals[:limit],'facts':facts,'checks':checks,'remaining':remaining,'work_items':works,
                        'work_items_truncated':works_truncated,
                        'next_cursor':f'{sequence}:{offset+limit}' if len(goals)>limit else None,
                        'view':{'result':'현재 기록','checks':'확인','remaining':'남은 일'}}
    require(len(encoded(result).encode())<=512000,'RESPONSE_TOO_LARGE','Narrow the goal or page size')
    return result
