"""Pure input normalization. A parser's role inference is never host authority."""
import json
import re
import shlex
from .common import digest
from .errors import require

ACTS={'answer','investigate','decide','requirements','design','tasks','implement','validate','deploy','resume','cancel'}
OUTPUTS={'answer':[], 'investigate':['observation','evidence'], 'decide':['decision'], 'requirements':['requirement'], 'design':['plan'], 'tasks':['work_item'], 'implement':['execution','evidence'], 'validate':['evidence'], 'deploy':['execution','evidence'], 'resume':[], 'cancel':[]}

def normalize(value,project):
    require(isinstance(value,str) and len(value.encode())<=256000,'INVALID_INPUT','Bounded input text required')
    parts=[];fenced=False;targets=[];offset=0
    for line in value.splitlines(keepends=True):
        start=offset;offset+=len(line)
        role='user_instruction';ref=None
        if line.lstrip().startswith('```'):
            fenced=not fenced;role='quoted_material'
        elif fenced or line.lstrip().startswith('>'):role='quoted_material'
        elif re.match(r'^\s*[/$]skip\s+--project\b',line):
            require(not any(x in line for x in (';','&&','||','`','$(')),'INVALID_INPUT','Selector is data, not shell code')
            try:args=shlex.split(line)
            except ValueError:raise ValueError('Malformed record selector')
            require(len(args)==7 and args[1]=='--project' and args[3:6]==['query','record','--input'],'INVALID_INPUT','Unsupported record selector')
            require(args[2]==project,'PROJECT_MISMATCH','Selector belongs to another project')
            try:ref=json.loads(args[6])
            except ValueError:raise ValueError('Malformed selector JSON')
            require(isinstance(ref,dict) and set(ref)=={'kind','id','revision'} and ref['kind'] in ('goal','decision','requirement','plan','work_item','evidence') and isinstance(ref['id'],str) and type(ref['revision']) is int and ref['revision']>0,'INVALID_INPUT','Exact record revision required')
            targets.append(ref);require(len(targets)==1,'AMBIGUOUS_INPUT','Multiple selectors need an explicit target')
            role='record_reference'
        elif line.lstrip().startswith(('<environment_context>','<recommended_plugins>','<skill>')):role='unknown'
        chunks=[(0,len(line),role)]
        if role=='user_instruction':
            chunks=[];cursor=0
            for match in re.finditer(r"`[^`]*`|\"[^\"]*\"|'[^']*'|“[^”]*”|‘[^’]*’",line):
                if match.start()>cursor:chunks.append((cursor,match.start(),role))
                chunks.append((match.start(),match.end(),'quoted_material'));cursor=match.end()
            if cursor<len(line):chunks.append((cursor,len(line),role))
        for left,right,part_role in chunks:
            parts.append({'part_id':str(len(parts)), 'role':part_role,'role_basis':'parser','start':start+left,'end':start+right,'text':line[left:right],'record_ref':ref})
    return {'schema':'skip-input/v1','digest':digest(value),'parts':parts,'targets':targets}

def classify(envelope):
    """Conservative suggested acts. Complex semantics can be proposed separately."""
    value=''.join(p['text'] for p in envelope['parts'] if p['role']=='user_instruction').strip()
    constraints=[]
    if re.search(r'설계\s*변경.{0,8}(말|않|금지)',value):constraints.append('design_change')
    if re.search(r'배포.{0,10}(말|않|아직|금지)|do not deploy',value,re.I):constraints.append('deploy')
    if re.search(r'(구현|수정|코드\s*변경).{0,8}(하지|말고|금지)|do not (implement|edit)',value,re.I):constraints.append('implement')
    cleaned=re.sub(r'설계\s*변경.{0,8}?말고','',value)
    if not value:acts=['answer']
    elif re.search(r'위험하지|왜|어떻게|상태|진행\s*상황|\?\s*$',value):acts=['investigate']
    elif re.fullmatch(r'(계속해|계속 진행해|continue|proceed)[.!\s]*',value,re.I):acts=['resume']
    elif re.fullmatch(r'(취소해|중지해|cancel|stop)[.!\s]*',value,re.I):acts=['cancel']
    elif re.search(r'상세\s*구현\s*계획|작업\s*분해|\btasks\b',value,re.I):acts=['tasks']
    elif re.search(r'구현\s*(해|하자|하세요|시작|진행)|수정해|고쳐|\b(implement|fix)\b',cleaned,re.I) and 'implement' not in constraints:acts=['implement']
    elif re.search(r'설계|\bdesign\b',value,re.I):acts=['design']
    elif re.search(r'요구사항|\brequirements\b',value,re.I):acts=['requirements']
    elif re.search(r'계획|검토|분석|\b(plan|review|analyze)\b',value,re.I):acts=['design' if '계획' in value else 'investigate']
    elif re.search(r'배포해|\bdeploy\b',value,re.I) and 'deploy' not in constraints:acts=['deploy']
    elif re.search(r'검증해|\bvalidate\b',value,re.I):acts=['validate']
    else:acts=['answer']
    spans=[{'part_id':p['part_id'],'start':p['start'],'end':p['end']} for p in envelope['parts'] if p['role']=='user_instruction' and p['text'].strip()]
    return {'acts':acts,'constraints':constraints,'targets':envelope['targets'],'evidence_spans':spans,'unresolved':[], 'basis':'parser_suggestion','semantic_guarantee':False}
