"""Generate the public contract from the Core's typed operation registry."""
import json
from pathlib import Path
from skip_core.service import OPERATIONS
from skip_core.records import FIELDS,CHILDREN

def contract():
    variants=[]
    for name,(required,optional,human) in OPERATIONS.items():
        properties={key:{} for key in required|optional}
        variants.append({'type':'object','additionalProperties':False,'required':['schema','command','key','project_id','payload'],
          'properties':{'schema':{'const':'skip-core/v1'},'command':{'const':name},'key':{'$ref':'#/$defs/id'},'project_id':{'$ref':'#/$defs/id'},
                        'payload':{'type':'object','required':sorted(required),'additionalProperties':False,'properties':properties}},
          'description':'Verified native user action required' if human else 'Agent command; no human authority'})
    definitions={'id':{'type':'string','pattern':'^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$'},
                 'command':{'oneOf':variants},
                 'response':{'type':'object','required':['schema','status','enforcement'],
                    'properties':{'schema':{'const':'skip-core/v1'},'status':{'enum':['ok','error']},'enforcement':{'const':'advisory'},
                                  'data':{'type':'object'},'project_id':{'$ref':'#/$defs/id'},'sequence':{'type':'integer','minimum':0},
                                  'code':{'type':'string'},'error':{'type':'string'}},'additionalProperties':False}}
    for kind,fields in FIELDS.items():
        definitions[kind]={'type':'object','required':list(fields),'additionalProperties':False,
                           'properties':{f:{'type':'string','minLength':1,'maxLength':65536} for f in fields}}
        for key,(_,_,_,columns) in CHILDREN[kind].items():
            definitions[kind+'_'+key]={'type':'object','required':list(columns),'additionalProperties':False,'properties':{
                col:({'type':'integer','minimum':1} if col.endswith('_revision') else {'type':'integer','enum':[0,1]} if col in ('required','recommended')
                else {'type':'integer','minimum':0} if col=='position' else {'type':'string','maxLength':65536}) for col in columns}}
    return {'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://skip.local/schemas/core-v1',
            'title':'SKIP Core generation 1','$defs':definitions,'$ref':'#/$defs/command'}

def main():
    path=Path(__file__).resolve().parents[1]/'schemas/skip-core-v1.json'
    path.write_text(json.dumps(contract(),ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':main()
