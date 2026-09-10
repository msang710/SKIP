"""Agent-oriented authoring. One public call, one Core transaction, no authority promotion."""
import copy
import sqlite3
from . import records
from .common import encoded,uid
from .errors import CoreError,require

OPS={
 'authoring.submit':({'base','records'},set(),False),
 'authoring.amend':({'base','changes'},set(),False),
 'authoring.result':({'base','snapshot_id','evidence'},{'execution_id','now','failure'},False),
}
KINDS={'decision','requirement','plan','work_item'}
KEYS={'options':('option_id',),'criteria':('criterion_id',),'checks':('check_id',),'items':('item_id',),'requirements':('requirement_id',),'decisions':('decision_id',),'selections':('selection_id',),'plan_items':('plan_id','plan_item_id'),'dependencies':('depends_on_id',)}
REFS={'requirement_id':('requirement','requirement_revision'),'decision_id':('decision','decision_revision'),'plan_id':('plan','plan_revision'),'depends_on_id':('work_item','depends_on_revision')}

def base(core,p):
 b=p['base'];require(isinstance(b,dict) and set(b)=={'goal_id','request_id'},'INVALID_INPUT','base requires goal_id and request_id')
 g=records.get(core.c,core.project,'goal',b['goal_id'])
 require(g['lifecycle']=='active','STALE','Goal is not active')
 require(core.c.execute('SELECT 1 FROM request_goals WHERE project_id=? AND request_id=? AND goal_id=?',(core.project,b['request_id'],b['goal_id'])).fetchone(),'PROJECT_MISMATCH','Request is not linked to this goal')
 return b

def receipt(saved):
 complete=len(encoded(saved).encode())<=128000
 if not complete:
  saved=[{k:v for k,v in r.items() if k in ('client_ref','outcome','kind','id','revision','digest')} for r in saved]
 return {'committed':True,'complete':complete,'records':saved,'authority':'records_only',
         'next_action':'Use the saved records; no confirmation read required.' if complete else 'Saved; expand exact record kind/id/revision only when its omitted content is needed.'}

def scoped(core,b,r):
 require(r['goal_id']==b['goal_id'],'PROJECT_MISMATCH','Record outside authoring goal')
 return r

def children(core,b,kind,groups,aliases,existing=None):
 require(isinstance(groups,dict) and set(groups)<=set(records.CHILDREN[kind]),'INVALID_INPUT','Unknown child group')
 output=copy.deepcopy(groups)
 for group,rows in output.items():
  require(isinstance(rows,list) and len(rows)<=128,'INVALID_INPUT','Bounded child array required')
  for i,row in enumerate(rows):
   require(isinstance(row,dict),'INVALID_INPUT','Child must be an object')
   if group in ('options','criteria','checks','items'):
    row.setdefault(KEYS[group][0],uid())
    if group in ('options','items'):
     previous=next((r for r in (existing or {}).get(group,[]) if r[KEYS[group][0]]==row[KEYS[group][0]]),None)
     row.setdefault('position',previous['position'] if previous else max([r['position'] for r in (existing or {}).get(group,[])],default=-1)+1+i)
   if 'selection_id' in row:
    selection=core.one('selections',row['selection_id'])
    scoped(core,b,records.get(core.c,core.project,'decision',selection['decision_id'],selection['decision_revision']))
   for key,(target_kind,revision_key) in REFS.items():
    if key not in row:continue
    value=row[key]
    if isinstance(value,str) and value.startswith('$'):
     require(value[1:] in aliases,'INVALID_INPUT','Reference must name an earlier record in the bundle')
     target=aliases[value[1:]]
     require(target['kind']==target_kind,'INVALID_INPUT','Reference kind mismatch')
     require(revision_key not in row,'INVALID_INPUT','Local reference resolves its own revision')
     row[key]=target['id'];row[revision_key]=target['revision']
    else:
     require(revision_key in row,'INVALID_INPUT','Existing reference needs an exact revision')
     scoped(core,b,records.get(core.c,core.project,target_kind,row[key],row[revision_key]))
   require(set(row)==set(records.CHILDREN[kind][group][3]),'INVALID_INPUT',f'Invalid fields in children.{group}[{i}]')
 return output

def located(fn,path):
 try:return fn()
 except sqlite3.IntegrityError as e:
  raise CoreError('INVALID_INPUT','Invalid record relationship or required child constraint',details={'input_path':path,'constraint':str(e)}) from e
 except CoreError as e:
  raise CoreError(e.code,str(e),details={**(e.details or {}),'input_path':path}) from e

def submit(core,p):
 b=base(core,p);items=p['records'];require(isinstance(items,list) and 0<len(items)<=64,'INVALID_INPUT','Submit 1 to 64 records')
 aliases={};saved=[]
 for i,item in enumerate(items):
  def one():
   require(isinstance(item,dict) and {'client_ref','kind','fields'}<=set(item)<= {'client_ref','kind','fields','children'},'INVALID_INPUT','Invalid submission item')
   key=item['client_ref'];kind=item['kind']
   require(isinstance(key,str) and key and key not in aliases and kind in KINDS,'INVALID_INPUT','Unique client_ref and authorable kind required')
   fields=copy.deepcopy(item['fields']);require(isinstance(fields,dict),'INVALID_INPUT','Fields object required')
   if kind=='work_item':
    require('request_id' not in fields,'INVALID_INPUT','Work request_id is supplied by base; omit it')
    fields['request_id']=b['request_id']
   ch=children(core,b,kind,item.get('children',{}),aliases)
   r=core._record_propose_revision({'kind':kind,'expected_revision':0,'request_id':b['request_id'],'goal_id':b['goal_id'],'fields':fields,'children':ch})
   aliases[key]=r;return {'client_ref':key,'outcome':'created',**r}
  saved.append(located(one,f'records[{i}]'))
 return receipt(saved)

def amend(core,p):
 b=base(core,p);changes=p['changes'];require(isinstance(changes,list) and 0<len(changes)<=64,'INVALID_INPUT','Amend 1 to 64 records')
 saved=[];seen=set()
 for i,change in enumerate(changes):
  def one():
   require(isinstance(change,dict) and {'target'}<=set(change)<={'target','set_fields','upsert_items','remove_items'},'INVALID_INPUT','Invalid amendment')
   t=change['target'];require(isinstance(t,dict) and set(t)=={'kind','id','revision'} and t['kind'] in KINDS,'INVALID_INPUT','Exact authorable target required')
   key=(t['kind'],t['id']);require(key not in seen,'INVALID_INPUT','One amendment per target');seen.add(key)
   old=scoped(core,b,records.get(core.c,core.project,t['kind'],t['id'],t['revision']))
   if old['current_revision']!=t['revision']:
    raise CoreError('STALE','Target changed; refresh only this target',details={'target':t,'current_revision':old['current_revision']})
   fields=copy.deepcopy(old['fields']);patch=change.get('set_fields',{})
   require(isinstance(patch,dict) and set(patch)<=set(fields)-{'request_id'},'INVALID_INPUT','Unknown field patch')
   fields.update(patch);ch=copy.deepcopy(old['children'])
   require(isinstance(change.get('remove_items',{}),dict),'INVALID_INPUT','remove_items must be an object')
   for group,keys in change.get('remove_items',{}).items():
    require(group in ch and isinstance(keys,list),'INVALID_INPUT','Unknown child group')
    for selector in keys:
     require(isinstance(selector,dict) and set(selector)==set(KEYS[group]),'INVALID_INPUT','Stable child keys required')
     matches=[r for r in ch[group] if all(r[k]==v for k,v in selector.items())]
     require(len(matches)==1,'CONFLICT','Removal key missing or ambiguous')
     ch[group].remove(matches[0])
   additions=children(core,b,t['kind'],change.get('upsert_items',{}),{},existing=ch)
   for group,rows in additions.items():
    for row in rows:
     matches=[r for r in ch[group] if all(r[k]==row[k] for k in KEYS[group])]
     require(len(matches)<=1,'CONFLICT','Ambiguous child key')
     if matches:ch[group][ch[group].index(matches[0])]=row
     else:ch[group].append(row)
   if fields==old['fields'] and ch==old['children']:return {'outcome':'unchanged',**old}
   # Preserve original work request: editing its content is not a new execution request.
   payload={'kind':t['kind'],'id':t['id'],'expected_revision':t['revision'],'request_id':b['request_id'],'goal_id':b['goal_id'],'fields':fields,'children':ch}
   if t['kind']=='work_item':payload['request_id']=fields['request_id']
   r=core._record_propose_revision(payload)
   return {'outcome':'changed','affected_records':dependents(core,t),
           'authority_note':'Exact dependencies are retained, not rebound or approved. Review affected records before execution.',**r}
  saved.append(located(one,f'changes[{i}]'))
 return receipt(saved)

def dependents(core,target):
 found={}
 for kind,groups in records.CHILDREN.items():
  for group,(table,owner,version,columns) in groups.items():
   for key,(ref_kind,rev_key) in REFS.items():
    if ref_kind!=target['kind'] or key not in columns:continue
    for row in core.c.execute(f'SELECT DISTINCT r.{owner} AS id,r.{version} AS revision FROM {table} r JOIN {kind}s h ON h.project_id=r.project_id AND h.id=r.{owner} AND h.current_revision=r.{version} WHERE r.project_id=? AND r.{key}=? AND r.{rev_key}=?',(core.project,target['id'],target['revision'])):
     found[(kind,row['id'])]={'kind':kind,'id':row['id'],'revision':row['revision']}
 return list(found.values())

def result(core,p):
 b=base(core,p);snapshot=core.one('snapshots',p['snapshot_id']);scope=core.one('scopes',snapshot['scope_id'])
 require(scope['goal_id']==b['goal_id'],'PROJECT_MISMATCH','Snapshot outside goal')
 ev=copy.deepcopy(p['evidence']);require(isinstance(ev,dict) and {'surface','result','summary','method'}<=set(ev)<={'surface','result','summary','method','checks','criteria','payload','purpose'},'INVALID_INPUT','Invalid evidence result')
 ev['snapshot_id']=p['snapshot_id']
 if p.get('execution_id'):
  x=core.one('executions',p['execution_id']);scoped(core,b,records.get(core.c,core.project,'work_item',x['work_item_id'],x['work_revision']))
  ev['execution_id']=x['id']
 from .evidence import record as record_evidence
 for group in ('checks','criteria'):
  require(isinstance(ev.get(group,[]),list) and all(isinstance(r,dict) for r in ev.get(group,[])),'INVALID_INPUT','Evidence links must be arrays of objects')
 for criterion in ev.get('criteria',[]):
  require({'requirement_id','requirement_revision'}<=set(criterion),'INVALID_INPUT','Exact criterion requirement required')
  scoped(core,b,records.get(core.c,core.project,'requirement',criterion['requirement_id'],criterion['requirement_revision']))
 evidence=located(lambda:record_evidence(core,ev,auto_failure=False),'evidence');out={'committed':True,'complete':True,'evidence':evidence,'authority':'agent_report','execution_finished':False}
 if 'failure' in p:
  from . import failures,learning
  f=p['failure'];require(isinstance(f,dict) and {'classification'}<=set(f)<={'classification','expected','conditions','case_id','action'},'INVALID_INPUT','Invalid failure description')
  require(f['classification'] in ('product','tool','reported','injected','unclassified'),'INVALID_INPUT','Unknown failure classification')
  if f.get('case_id') and ev['result']=='PASS':
   case=learning.get(core,'failure',f['case_id'])
   require(case['goal_id']==b['goal_id'],'PROJECT_MISMATCH','Case outside goal')
   require(f.get('action'),'INVALID_INPUT','Successful recovery requires its action description')
  else:
   report=failures.report(core,{'evidence_id':evidence['evidence_id'],**{k:v for k,v in f.items() if k!='action'}})
   case=learning.get(core,'failure',report['case_id'])
  body=dict(case['body'])
  for k in ('expected','conditions'):
   if k in f:body[k]=f[k]
  if body!=case['body']:
   case=learning.propose(core,{'kind':'failure','id':case['id'],'expected_revision':case['revision'],'goal_id':b['goal_id'],'body':body})
  out['failure']=case
  if f.get('action'):out['attempt']=failures.attempt(core,{'case_id':case['id'],'evidence_id':evidence['evidence_id'],'action':f['action']})
 if 'now' in p:
  n=p['now'];require(isinstance(n,dict) and {'statement','source_id'}<=set(n)<={'statement','source_id','supersedes_id'},'INVALID_INPUT','Explicit current fact required')
  out['now']=core._fact_record({'evidence_id':evidence['evidence_id'],'goal_id':b['goal_id'],**n})
 return out

HANDLERS={'authoring.submit':submit,'authoring.amend':amend,'authoring.result':result}
