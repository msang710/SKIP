"""One-time semantic repair, from the preserved DB originals into native Core records.

No source tree inference. Exact documented IDs/text/links/status are used. Missing
fields and ambiguous references are reported, never synthesized as approvals.
"""
import argparse, collections, hashlib, json, re, sqlite3, sys
from pathlib import Path, PurePosixPath
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import yaml
from skip_core.db import Database
from skip_core import records
from skip_core.common import digest, encoded, now, uid

TERMINAL={'completed','complete','done','superseded','rejected','revoked','완료','대체','대체됨','반려','철회'}
ID=r'(?:D|R|T|AC|US)(?:-[A-Z]+)*-\d+(?:-\d+)*[A-Z]?'
MISSING='원문에 명시되지 않음'

def terminal(value):
    return re.split(r'\s*[—:：]\s*',str(value).strip().lower())[0] in TERMINAL

def parse_document(row):
    d=dict(row)
    try: raw=bytes(d['content']).decode('utf-8-sig').replace('\r\n','\n')
    except UnicodeDecodeError: raw=''
    meta=json.loads(d['metadata_json']);body=raw
    m=re.match(r'^\s*---\n(.*?)\n---\s*\n?',raw,re.S)
    if m:
        try: meta.update(yaml.safe_load(m[1]) or {})
        except yaml.YAMLError: pass
        body=raw[m.end():]
    # Earlier QuickHack records use a plain metadata preamble, not frontmatter.
    for line in body.splitlines()[:18]:
        m=re.match(r'^(status|상태|title|updated|created|source_revision):\s*(.+)$',line,re.I)
        if m:meta['status' if m[1].lower()=='상태' else m[1].lower()]=m[2]
    d.update(meta=meta,body=body,status=str(meta.get('status') or d['historical_status']),group=str(PurePosixPath(d['source_path']).parent))
    return d

def sections(body):
    lines=body.splitlines(); result=[];start=0;heading='본문';fence=False
    for i,line in enumerate(lines):
        if re.match(r'^\s*(```|~~~)',line):fence=not fence
        m=re.match(r'^#{1,6}\s+(.+)',line) if not fence else None
        if m:
            if i>start:result.append((heading,'\n'.join(lines[start:i]).strip()))
            heading=m[1];start=i
    if start<len(lines):result.append((heading,'\n'.join(lines[start:]).strip()))
    return result

def pick(body,pattern,default=MISSING):
    parts=[text for title,text in sections(body) if re.search(pattern,title,re.I)]
    return '\n\n'.join(parts)[:64000] or default

def cells(line):return [v.strip() for v in re.split(r'(?<!\\)\|',line.strip().strip('|'))]

def items(body,letter):
    """Extract only explicit ID definitions, retaining table headings and full blocks."""
    out=[]; lines=body.splitlines();headers=[];fence=False;i=0
    pattern=rf'{letter}(?:-[A-Z]+)*-\d+(?:-\d+)*[A-Z]?'
    while i<len(lines):
        line=lines[i]
        if re.match(r'^\s*(```|~~~)',line):fence=not fence;i+=1;continue
        if fence:i+=1;continue
        if line.startswith('|'):
            row=cells(line)
            m=re.match(rf'^`?({pattern})\b',row[0])
            if m:
                data=dict(zip(headers,row)) if len(headers)==len(row) else {}
                out.append({'key':m[1],'title':row[0] if row[0]!=m[1] else next((v for k,v in data.items() if re.search(r'^(decision|결정|requirement|요구사항|규칙|task|작업)$',k,re.I)),row[1] if len(row)>1 else row[0]),'body':'| '+' | '.join(headers)+' |\n'+line,'data':data,'priority':2})
            elif i+1<len(lines) and re.match(r'^\|[\s:|\-]+\|$',lines[i+1]):headers=row
            i+=1;continue
        m=re.match(rf'^(?:#{{1,6}}\s+|[-*]\s+(?:\[[ xX]\]\s+)?|)\**`?({pattern})\b',line)
        if m:
            j=i+1
            while j<len(lines) and not re.match(r'^(?:#{1,6}\s+|[-*]\s+(?:\[[ xX]\]\s+)?)'+ID+r'\b',lines[j]) and not re.match(r'^#{1,6}\s+',lines[j]):j+=1
            block='\n'.join(lines[i:j]).strip();out.append({'key':m[1],'title':re.sub(r'^[#*\s-]+','',line).strip(),'body':block,'data':{},'priority':3 if line.startswith('#') else 1});i=j
        else:i+=1
    grouped=collections.defaultdict(list)
    for item in out:grouped[item['key']].append(item)
    definitions=[]
    for key,values in grouped.items():
        priority=max(v['priority'] for v in values)
        candidates=[v for v in values if v['priority']==priority]
        chosen=dict(candidates[0])
        chosen['body']='\n\n'.join(v['body'] for v in candidates)
        for v in values:
            for label,value in v['data'].items():
                if re.fullmatch('status|상태',label,re.I):chosen['data'][label]=value
        definitions.append(chosen)
    return definitions

def field(item,pattern,default=MISSING):
    return next((v for k,v in item['data'].items() if re.search(pattern,k,re.I)),default)

def item_status(item,default):
    state=field(item,r'^(status|상태)$','')
    if state:return state
    m=re.search(r'^\s*[-*]?\s*(?:상태|Status):\s*(.+)',item['body'],re.I|re.M)
    if m:return m[1]
    if re.search(r'^[-*]\s+\[[xX]\]',item['body']):return 'completed'
    # Combined reason/status columns contain explicit recorded status tokens.
    for value in item['data'].values():
        m=re.search(r'\b(confirmed|superseded|rejected|proposed|open)\b',value,re.I)
        if m:return m[1]
    return default

def record_id(d,kind,key):return 'record-'+digest([d['project_id'],d['goal_id'],d['group'],kind,key])[:36]

def prepare(c):
    docs=[parse_document(r) for r in c.execute('select * from imported_documents order by project_id,source_path')]
    for d in docs:
        d['excluded']=terminal(d['status'])
        d['reason']='문서에 명시된 종료 상태: '+d['status'] if d['excluded'] else ''
        if d['source_path'].startswith('legacy/'):
            d['excluded']=True;d['reason']='프로젝트 업무 기록이 아닌 이전 스킬/계약 사본'
    # Only explicit goal lifecycle terminates all its children. Approval is not lifecycle.
    ended={}
    for d in docs:
        if d['source_path'].endswith('projection.yaml') and terminal(d['meta'].get('lifecycle','')):
            ended[d['project_id'],d['goal_id']]=str(d['meta']['lifecycle'])
    for d in docs:
        if (d['project_id'],d['goal_id']) in ended:d['excluded']=True;d['reason']='목표 종료: '+ended[d['project_id'],d['goal_id']]
    return docs

class Repair:
    def __init__(self,c,docs):
        self.c=c;self.docs=docs;self.stamp=now();self.projects={};self.origins=0;self.missing=[];self.counts=collections.Counter()
    def event(self,p,kind,payload=None):
        interaction,seq=self.projects[p];seq+=1;self.projects[p]=(interaction,seq);ident=uid()
        records.insert(self.c,'events',dict(project_id=p,id=ident,sequence=seq,interaction_id=interaction,command_key=ident,command_digest=digest(payload or {}),kind=kind,payload_json=encoded(payload or {}),created_at=self.stamp))
        return ident
    def origin(self,d,kind,ident,rev,key,status,excerpt,issues=(),classification=None):
        records.insert(self.c,'record_origins',dict(project_id=d['project_id'],kind=kind,record_id=ident,revision=rev,document_id=d['id'],source_key=key,source_status=status,source_date=str(d['meta'].get('updated') or d['meta'].get('created') or '') or None,classification=classification,source_excerpt=excerpt,unresolved_json=encoded(list(issues))))
        self.origins+=1;self.counts[kind]+=1
    def publish(self,d,kind,key,fields,children=None,status=None,issues=(),ident=None):
        p=d['project_id'];g=d['goal_id'];ident=ident or record_id(d,kind,key)
        head=self.c.execute('select * from '+kind+'s where project_id=? and id=?',(p,ident)).fetchone()
        request=self.c.execute('select origin_request_id from goals where project_id=? and id=?',(p,g)).fetchone()[0]
        payload={'kind':kind,'id':ident,'request_id':request,'goal_id':g,'expected_revision':head['current_revision'] if head else 0,'fields':fields,'children':children or {}}
        origin=dict(document_id=d['id'],source_key=key,source_status=status or d['status'],source_date=str(d['meta'].get('updated') or d['meta'].get('created') or '') or None,classification=d.get('classification'),source_excerpt=key,unresolved_json=encoded(list(issues)))
        i,rev=records.publish(self.c,p,payload,self.event(p,'maintenance.record_restored'),record_origin=origin)
        records.advance(self.c,p,kind,i,rev,self.event(p,'maintenance.record_available'))
        self.origins+=1;self.counts[kind]+=1
        return i,rev
    def archive(self,p,kind,ident):
        self.c.execute('update '+kind+'s set lifecycle=?,state_version=state_version+1,last_event_id=? where project_id=? and id=?',('archived',self.event(p,'maintenance.replaced_projection'),p,ident))
    def run(self):
        assert not self.c.execute('select 1 from document_dispositions').fetchone(),'Repair already applied'
        for p, in self.c.execute('select id from projects').fetchall():
            interaction=uid();body='사용자 요청에 따른 재이관: 완료·대체·반려 문서 제외, 실제 목표·결정·요구사항·설계·작업·검증 복원.'
            records.insert(self.c,'interactions',dict(project_id=p,id=interaction,origin_context_digest=digest(['semantic-reimport',p]),external_event_key=interaction,actor_kind='agent',body=body,body_digest=hashlib.sha256(body.encode()).hexdigest(),created_at=self.stamp))
            self.projects[p]=(interaction,self.c.execute('select coalesce(max(sequence),0) from events where project_id=?',(p,)).fetchone()[0])
        # Replace only the first importer's synthetic heads, retaining their audit trail.
        for kind in ('requirement','plan'):
            for p,ident in self.c.execute('select distinct project_id,'+kind+'_id from imported_record_refs where '+kind+'_id is not null').fetchall():self.archive(p,kind,ident)
        grouped=collections.defaultdict(list)
        for d in self.docs:
            records.insert(self.c,'document_dispositions',dict(project_id=d['project_id'],document_id=d['id'],disposition='excluded' if d['excluded'] else 'supplement',reason=d['reason'] or '원문과 출처 보존',event_id=self.event(d['project_id'],'maintenance.document_classified')))
            if not d['excluded'] and d['goal_id'] and d['source_path'].endswith('.md'):grouped[d['project_id'],d['goal_id']].append(d)
        for (p,g),ds in grouped.items():self.goal(p,g,ds)
        for d in self.docs:
            if d['excluded'] or not d['source_path'].endswith('.md'):continue
            disposition=self.c.execute('select disposition from document_dispositions where project_id=? and document_id=?',(d['project_id'],d['id'])).fetchone()[0]
            if '/NOW/' in '/'+d['source_path'] or disposition=='supplement':self.observations(d)
        for p,g in self.c.execute('select project_id,id from goals').fetchall():
            if (p,g) not in grouped and self.c.execute('select 1 from imported_documents where project_id=? and goal_id=?',(p,g)).fetchone():self.archive(p,'goal',g)
        return {'counts':dict(self.counts),'excluded':[{'project_id':d['project_id'],'path':d['source_path'],'reason':d['reason']} for d in self.docs if d['excluded']],'unresolved_links':self.missing,'originals':len(self.docs)}
    def goal(self,p,g,ds):
        primary=next((d for d in ds if d['source_path'].endswith('/prd.md')),next((d for d in ds if '/NOW/' in '/'+d['source_path']),ds[0]))
        body=primary['body'];title=str(primary['meta'].get('title') or next((h for h,_ in sections(body) if h!='본문'),g))
        intent=pick(body,r'^(?:\d+[.)]\s*)?(?:goal|목표|문제|문제 정의|배경|제품 목표|current.*behavior|현재 구현|current.*outcome|current.*state|현재 상태)',body[:64000] or MISSING)
        success=pick(body,r'acceptance|수용|인수|완료 판단|success|검증|verification|완료 기준|목표 상태')
        self.publish(primary,'goal','goal',{'title':title,'intent':intent,'success_definition':success},ident=g)
        nodes=[]
        for d in ds:
            path=d['source_path'];body=d['body']
            if not path.endswith('.md') or '/NOW/' in '/'+path or '.skip/' in path:continue
            for letter,kind in [('D','decision'),('R','requirement'),('T','work_item')]:
                # ID definitions in source plans/specs; not incidental references in prose.
                if kind=='work_item' and 'task' not in PurePosixPath(path).stem and 'implementation' not in PurePosixPath(path).stem:continue
                for item in items(body,letter):
                    if kind=='decision' and d['kind']!='requirement' and not any(re.search(r'^(decision|결정)$',k,re.I) for k in item['data']):continue
                    if kind=='requirement' and d['kind']!='requirement':continue
                    item.update(d=d,kind=kind,status=item_status(item,d['status']))
                    if not terminal(item['status']) or (kind=='work_item' and item['status'].strip().lower() in ('completed','done','complete','완료')):nodes.append(item)
            if d['kind']=='plan':
                groups=[];chunk=[];size=0
                for heading,part in sections(body):
                    if size+len(part)>58000 or len(chunk)>=100:
                        if chunk:groups.append(chunk)
                        chunk=[];size=0
                    chunk.append((heading,part));size+=len(part)
                if chunk:groups.append(chunk)
                for number,parts in enumerate(groups):
                    title=str(d['meta'].get('title') or parts[0][0])
                    nodes.append({'d':d,'kind':'plan','key':PurePosixPath(path).stem+'-'+str(number),'title':title+(' · '+str(number+1) if len(groups)>1 else ''),'body':'\n\n'.join(part for _,part in parts),'status':d['status'],'data':{},'parts':parts})
            # Prose-only specifications still become native requirements, using their exact sections.
            if d['kind']=='requirement' and not items(body,'R'):
                for number,(heading,part) in enumerate(sections(body)):
                    if re.search(r'decision|결정|self.review|검토',heading,re.I):continue
                    if len(part.strip())<10:continue
                    nodes.append({'d':d,'kind':'requirement','key':PurePosixPath(path).stem+'-'+str(number),'title':heading,'body':part,'status':d['status'],'data':{}})
            if d['kind']=='work_item' and not items(body,'T'):
                for number,(heading,part) in enumerate(sections(body)):
                    if re.search('self.review|검토',heading,re.I) or len(part.strip())<10:continue
                    nodes.append({'d':d,'kind':'work_item','key':PurePosixPath(path).stem+'-'+str(number),'title':heading,'body':part,'status':d['status'],'data':{}})
        # Same explicit ID repeated in the same directory is ambiguous unless text is identical.
        index=collections.defaultdict(list)
        for n in nodes:index[n['d']['group'],n['kind'],n['key']].append(n)
        selected=[]
        for key,ns in index.items():
            unique={}
            for n in ns:unique.setdefault(n['body'],n)
            values=list(unique.values())
            for n in values:
                n['issues']=[]
                n['storage_key']=n['key'] if len(values)==1 else n['key']+'-'+digest(n['d']['source_path'])[:12]
                if len(values)>1:n['issues'].append('동일 ID의 다른 기록이 있어 문서별로 보존: '+', '.join(x['d']['source_path'] for x in values if x is not n))
                selected.append(n)
        resolved=collections.defaultdict(list)
        def refs(n,letter,kind):
            result=[]
            keys=set(re.findall(r'\b'+letter+r'(?:-[A-Z]+)*-\d+(?:-\d+)*[A-Z]?\b',n['body']))
            # Explicit numeric ranges (R-001 through R-005) are actual declared references.
            for a,b in re.findall(r'\b'+letter+r'-(\d+)\s*(?:through|~|부터|–|to)\s*'+letter+r'-(\d+)\b',n['body'],re.I):
                if 0<=int(b)-int(a)<=100:keys.update(letter+'-'+str(i).zfill(len(a)) for i in range(int(a),int(b)+1))
            for key in sorted(keys):
                choices=resolved.get((n['d']['group'],kind,key),[])
                same=[v for v in choices if v[2]==n['d']['source_path']]
                if len(same)==1:choices=same
                elif len(choices)>1 and PurePosixPath(n['d']['source_path']).name in ('tasks.md','system_design.md','user_stories.md','prd.md'):
                    canonical=[v for v in choices if PurePosixPath(v[2]).name=='prd.md']
                    if len(canonical)==1:choices=canonical
                if not choices:
                    choices=[v for (group,k,label),values in resolved.items() if k==kind and label==key and n['d']['group'].startswith(group+'/') for v in values]
                found=choices[0][:2] if len(choices)==1 else None
                if found:result.append((key,found))
                else:
                    issue={'project':p,'goal':g,'document':n['d']['source_path'],'from':n['key'],'target':key}
                    self.missing.append(issue);n['issues'].append('연결 대상 미확정: '+key)
            return result
        for kind in ('decision','requirement','plan','work_item'):
            for n in [n for n in selected if n['kind']==kind]:
                d=dict(n['d'],classification=field(n,r'classification|분류',None));text=n['body'][:64000];children={}
                if kind=='decision':
                    fields={'question':n['title'][:64000],'rationale':field(n,r'evidence|rationale|근거',text),'risk_summary':field(n,r'impact|영향|위험')}
                elif kind=='requirement':
                    fields={'title':n['title'][:1000],'statement':text,'rationale':field(n,r'근거|rationale',MISSING)}
                    acceptance=field(n,r'acceptance|수용|given|인수','')
                    m=re.search(r'Acceptance:\s*(.*)',text,re.S|re.I)
                    if m:acceptance=m[1]
                    children={'decisions':[{'decision_id':v[0],'decision_revision':v[1],'rationale':'원문 명시: '+key} for key,v in refs(n,'D','decision')]}
                    if acceptance:children['criteria']=[{'criterion_id':'acceptance','description':acceptance,'given_text':MISSING,'when_text':MISSING,'then_text':acceptance,'required':1}]
                elif kind=='plan':
                    fields={'title':n['title'],'design_body':text,'scope_description':pick(d['body'],r'scope|범위'),'alternatives_body':pick(d['body'],r'alternative|대안'),'rollback_body':pick(d['body'],r'rollback|복구|롤백')}
                    children={'items':[{'item_id':'part-'+str(pos),'title':heading,'design_body':part,'verification_body':pick(part,r'검증|verification|test'),'position':pos} for pos,(heading,part) in enumerate(n['parts'])],
                        'requirements':[{'requirement_id':v[0],'requirement_revision':v[1],'rationale':'원문 명시: '+key} for key,v in refs(n,'R','requirement')],
                        'decisions':[{'decision_id':v[0],'decision_revision':v[1],'rationale':'원문 명시: '+key} for key,v in refs(n,'D','decision')]}
                else:
                    def line_field(pattern):
                        m=re.search(r'^\s*[-*]?\s*(?:'+pattern+r')\s*[:：]\s*([^\n]*(?:\n[ \t]+[^\n]+)*)',text,re.I|re.M)
                        return m[1].strip() if m else MISSING
                    fields={'operation':'implement','title':n['title'][:1000],'instruction_body':text,'completion_definition':line_field('Completion conditions|완료 조건|종료|완료'),'workflow_depth':'full','request_id':self.c.execute('select origin_request_id from goals where project_id=? and id=?',(p,g)).fetchone()[0]}
                    verify=line_field('Verification|검증|검사')
                    children={'requirements':[{'requirement_id':v[0],'requirement_revision':v[1],'rationale':'원문 명시: '+key} for key,v in refs(n,'R','requirement')]}
                    if verify!=MISSING:children['checks']=[{'check_id':'verification','description':verify,'surface':'source','required':1}]
                    # Plans mention exact T IDs or tasks name explicit plan sections; no all-to-all links.
                    plans=[]
                    for plan in [x for x in selected if x['kind']=='plan' and x['d']['group']==d['group']]:
                        if re.search(r'\b'+re.escape(n['key'])+r'\b',plan['body']) or re.search(r'system_design\.md|시스템 설계|system design',text,re.I):
                            v=next((v[:2] for v in resolved.get((d['group'],'plan',plan['key']),[]) if v[2]==plan['d']['source_path']),None)
                            if v:
                                for pos,(heading,part) in enumerate(plan['parts']):
                                    if re.search(r'\b'+re.escape(n['key'])+r'\b',part) or re.search(r'system_design\.md|시스템 설계|system design',text,re.I):
                                        plans.append({'plan_id':v[0],'plan_revision':v[1],'plan_item_id':'part-'+str(pos),'rationale':'원문이 참조하는 설계: '+plan['d']['source_path']})
                    if plans:children['plan_items']=plans[:128]
                    # Dependencies are filled through revisions after all tasks exist.
                ident,rev=self.publish(d,kind,n['key'],fields,children,n['status'],n['issues'],ident=record_id(d,kind,n['storage_key']))
                n.update(ident=ident,revision=rev,fields=fields,children=children)
                resolved[d['group'],kind,n['key']].append((ident,rev,d['source_path']))
                if kind=='decision':
                    # Keep the original classification without inventing options or user selections.
                    pass
            if kind=='work_item':
                tasks=[x for x in selected if x['kind']=='work_item'];dep_map={}
                for n in tasks:
                    declared='\n'.join(l for l in n['body'].splitlines() if re.search('Dependencies|선행|의존',l,re.I))
                    dep_map[n['ident']]=[(key,v) for key,v in refs(dict(n,body=declared),'T','work_item') if v[0]!=n['ident']]
                pending={n['ident']:n for n in tasks if dep_map[n['ident']]};done=set()
                while pending:
                    ready=[n for ident,n in pending.items() if all(v[0] not in pending for _,v in dep_map[ident])]
                    if not ready:
                        raise ValueError('원문에 순환 작업 의존성이 있어 자동 이관할 수 없음: '+g)
                    for n in ready:
                        dependencies=[{'depends_on_id':v[0],'depends_on_revision':2 if dep_map.get(v[0]) else v[1],'reason':'원문 선행 작업: '+key} for key,v in dep_map[n['ident']]]
                        self.publish(n['d'],'work_item',n['key'],n['fields'],dict(n['children'],dependencies=dependencies),n['status'],n['issues'],ident=n['ident'])
                        del pending[n['ident']];done.add(n['ident'])
        for d in ds:
            if any(n['d']['id']==d['id'] for n in selected) or d['id']==primary['id']:
                self.c.execute("update document_dispositions set disposition='converted',reason='공통 Core 기록으로 복원' where project_id=? and document_id=?",(p,d['id']))
    def observations(self,d):
        p=d['project_id'];g=d['goal_id'];body=d['body']
        if not body:return
        scope=uid();snapshot=uid()
        records.insert(self.c,'scopes',dict(project_id=p,id=scope,goal_id=g,summary='원문에 기록된 관찰 범위: '+d['source_path'],digest=digest({'document':d['content_sha256']}),created_at=self.stamp))
        self.c.execute('update scopes set sealed_at=? where project_id=? and id=?',(self.stamp,p,scope))
        records.insert(self.c,'snapshots',dict(project_id=p,id=snapshot,scope_id=scope,digest=digest({'historical_document':d['content_sha256'],'source_revision':str(d['meta'].get('source_revision',''))}),created_at=self.stamp))
        self.c.execute('update snapshots set sealed_at=? where project_id=? and id=?',(self.stamp,p,snapshot))
        source=self.c.execute('select id from sources where project_id=? order by id limit 1',(p,)).fetchone()[0]
        for pos,(heading,part) in enumerate(sections(body)):
            if not part.strip():continue
            ident=uid();event=self.event(p,'maintenance.observation_restored');date=str(d['meta'].get('verified_at') or d['meta'].get('updated') or d['meta'].get('created') or '')
            # Mixed prose stays INCONCLUSIVE; per-line success is never inferred for an entire section.
            is_observation='/NOW/' in '/'+d['source_path']
            claims=set(re.findall(r'\b(PASS|FAIL|NOT_RUN|INCONCLUSIVE|EVIDENCE_PENDING|NOT_APPLICABLE|STALE)\b',part)) if is_observation else set()
            if is_observation and not claims and re.search(r'\bpassed\b|검사 통과|테스트 통과',part,re.I):claims={'PASS'}
            result=next(iter(claims)) if len(claims)==1 and next(iter(claims)) in ('PASS','FAIL','NOT_RUN','INCONCLUSIVE') else 'INCONCLUSIVE'
            records.insert(self.c,'evidence',dict(project_id=p,id=ident,snapshot_id=snapshot,execution_id=None,reporter_interaction_id=self.projects[p][0],surface='source',result=result,provenance='agent_report',summary=part[:64000],method='기존 기록의 관찰·검증 내용 보존: '+d['source_path'],observed_at=date or 'unknown',event_id=event,created_at=date or d['created_at']))
            blob=part.encode();records.insert(self.c,'evidence_payloads',dict(project_id=p,evidence_id=ident,part_id='original-section',media_type='text/markdown',content=blob,content_digest=hashlib.sha256(blob).hexdigest(),byte_length=len(blob)))
            self.c.execute('update evidence set sealed_at=? where project_id=? and id=?',(self.stamp,p,ident))
            self.origin(d,'evidence',ident,1,heading,' / '.join(sorted(claims)) if claims else d['status'],heading,classification=d['kind'])
            if '/NOW/' in '/'+d['source_path'] and result!='NOT_RUN' and re.search('current.*behavior|current.*outcome|current.*state|현재 구현|현재 상태|product behavior|implemented state|current implemented',heading,re.I):
                records.insert(self.c,'current_facts',dict(project_id=p,id=uid(),goal_id=g,statement=part[:64000],source_id=source,snapshot_id=snapshot,evidence_id=ident,event_id=event,created_at=date or d['created_at']))

        self.c.execute("update document_dispositions set disposition='converted',reason='공통 근거·관찰 기록으로 복원' where project_id=? and document_id=?",(p,d['id']))


def repair(path):
    with Database(path,create=True) as db:
        c=db.connection;before=[(r[0],r[1],r[2]) for r in c.execute('select project_id,id,content_sha256 from imported_documents')]
        with db.transaction():
            result=Repair(c,prepare(c)).run()
            assert not c.execute('pragma foreign_key_check').fetchall()
            assert before==[(r[0],r[1],r[2]) for r in c.execute('select project_id,id,content_sha256 from imported_documents')]
            for row in c.execute('select content,content_sha256 from imported_documents'):assert hashlib.sha256(row[0]).hexdigest()==row[1]
        assert c.execute('pragma integrity_check').fetchone()[0]=='ok'
        return result

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',type=Path,required=True);p.add_argument('--report',type=Path,required=True);a=p.parse_args()
    result=repair(a.db);a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v if k!='unresolved_links' else len(v) for k,v in result.items()},ensure_ascii=False))
