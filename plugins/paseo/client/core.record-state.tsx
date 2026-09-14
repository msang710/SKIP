import React,{useEffect,useState} from 'react';
import {View,Text,TextInput,Pressable} from 'react-native';
import {Action,tint} from './core.visual';

export const stateLabels:Record<string,string>={active:'활성',held:'보류',completed:'완료',rejected:'반려',superseded:'대체',archived:'보관'};
const documentKinds=['decision','requirement','plan','work_item'];
export function RecordStateMenu({record:r,theme,disabled,load,change,open}:{record:any;theme:any;disabled:boolean;load:(query:string,payload:any)=>Promise<any>;change:(payload:any)=>Promise<any>;open:(r:any)=>Promise<void>}) {
 const [base,setBase]=useState<any>(null);
 const [expanded,setExpanded]=useState(false),[mode,setMode]=useState<string|null>(null),[reason,setReason]=useState('');
 const [targets,setTargets]=useState<any[]>([]),[target,setTarget]=useState<any>(null),[cursor,setCursor]=useState<string|null>(null),[search,setSearch]=useState('');
 const [pending,setPending]=useState(false),[error,setError]=useState(''),[undo,setUndo]=useState<any>(null);
 const [history,setHistory]=useState<any[]|null>(null),[historyCursor,setHistoryCursor]=useState<string|null>(null);
 const color=theme.colors.foreground,muted=theme.colors.foregroundMuted;
 useEffect(()=>{setExpanded(false);setMode(null);setTarget(null);setTargets([]);setReason('');setUndo(null);setHistory(null);setError('');},[r.id]);
 if(!documentKinds.includes(r.kind))return null;
 const blocked=disabled||pending;
 async function run(action:()=>Promise<void>){setPending(true);setError('');try{await action();}catch(e){setError(e instanceof Error?e.message:'상태를 변경하지 못했습니다.');}finally{setPending(false);}}
 const action=(label:string,fn:()=>Promise<void>,off=false)=><Action theme={theme} label={label} accessibilityLabel={label} disabled={blocked||off} onPress={()=>void run(fn)}/>;
 async function candidates(append=false){
  const result=await load('record.list',{kind:r.kind,goal_id:r.goal_id,search,limit:30,...(append&&cursor?{cursor}:{})});
  setTargets(old=>[...(append?old:[]),...result.data.items.filter((v:any)=>v.id!==r.id&&v.lifecycle==='active')]);setCursor(result.data.next_cursor);
 }
 async function save(to:string){
  const original=base??r;
  const result=await change({kind:original.kind,id:original.id,revision:original.revision,state_version:original.state_version,from_state:original.lifecycle,to_state:to,...(['rejected','superseded'].includes(to)?{reason:reason.trim()}:{}),...(to==='superseded'?{replacement:{kind:r.kind,id:target.id,revision:target.revision}}:{})});
  setUndo(result);setExpanded(false);setMode(null);setReason('');setTarget(null);setHistory(null);
 }
 async function showHistory(append=false){const result=await load('record.state_history',{kind:r.kind,id:r.id,limit:20,...(append&&historyCursor?{cursor:historyCursor}:{})});setHistory(old=>[...(append?old??[]:[]),...result.data.items]);setHistoryCursor(result.data.next_cursor);}
 return <View style={{gap:8}}>
  <View style={{flexDirection:'row',alignItems:'center',gap:8}}>
   <Text style={{color:muted,flex:1}}>{stateLabels[r.lifecycle]??r.lifecycle}</Text>
   <Pressable accessibilityRole="button" accessibilityLabel="문서 상태 변경" accessibilityState={{expanded,disabled:blocked}} disabled={blocked} onPress={()=>{setExpanded(!expanded);setMode(null);setBase(r);}} style={{padding:8}}><Text style={{color,fontSize:20}}>⋯</Text></Pressable>
  </View>
  {r.state_change?.reason?<Text style={{color}}>{r.state_change.reason}</Text>:null}
  {r.state_change?.replacement?action('대체 문서 보기',()=>open(r.state_change.replacement)):null}
  {expanded?<View style={{gap:8,padding:10,borderWidth:1,borderColor:tint(muted,'30'),borderRadius:5}}>
   <View style={{flexDirection:'row',flexWrap:'wrap',gap:6}}>{['active','held','rejected','superseded','archived'].filter(s=>s!==r.lifecycle).map(s=><React.Fragment key={s}>{action(s==='active'?'다시 활성화':s==='superseded'?'다른 문서로 대체':stateLabels[s],async()=>{if(s==='rejected'||s==='superseded'){setMode(s);setReason('');setTarget(null);if(s==='superseded')await candidates();}else await save(s);})}</React.Fragment>)}</View>
   {mode?<>
    <TextInput accessibilityLabel={mode==='rejected'?'반려 이유':'대체 이유'} placeholder={mode==='rejected'?'반려 이유':'대체 이유'} placeholderTextColor={muted} value={reason} onChangeText={setReason} multiline editable={!blocked} style={{color,padding:8,borderWidth:1,borderColor:tint(muted,'30')}}/>
    {mode==='superseded'?<>
     <View style={{flexDirection:'row',gap:6}}><TextInput accessibilityLabel="대체 문서 검색" placeholder="같은 목표의 문서 검색" placeholderTextColor={muted} value={search} onChangeText={setSearch} editable={!blocked} style={{color,flex:1,padding:8}}/>{action('대체 문서 검색',()=>candidates())}</View>
     {targets.map(t=><Pressable key={t.id} accessibilityRole="radio" accessibilityLabel={t.title} accessibilityState={{checked:target?.id===t.id,disabled:blocked}} disabled={blocked} onPress={()=>setTarget(t)} style={{padding:8,backgroundColor:target?.id===t.id?tint(theme.colors.accent,'20'):undefined}}><Text style={{color}}>{t.title} · v{t.revision}</Text></Pressable>)}
     {!targets.length?<Text style={{color:muted}}>선택할 활성 문서가 없습니다.</Text>:null}
     {cursor?action('대체 후보 더 보기',()=>candidates(true)):null}
    </>:null}
    {action('상태 저장',()=>save(mode),!reason.trim()||(mode==='superseded'&&!target))}
   </>:null}
   {action(history?'변경 이력 접기':'변경 이력',async()=>{if(history)setHistory(null);else await showHistory();})}
   {history?.map(h=><View key={h.id} style={{gap:4}}><Text style={{color:muted}}>{stateLabels[h.from_state]} → {stateLabels[h.to_state]} · {h.created_at}</Text>{h.reason?<Text style={{color}}>{h.reason}</Text>:null}{h.replacement?action('이력의 대체 문서 보기',()=>open(h.replacement)):null}</View>)}
   {history&&!history.length?<Text style={{color:muted}}>상태 변경 이력이 없습니다.</Text>:null}
   {history&&historyCursor?action('변경 이력 더 보기',()=>showHistory(true)):null}
  </View>:null}
  {undo?<View style={{flexDirection:'row',alignItems:'center',gap:8}}><Text accessibilityLiveRegion="polite" style={{color:muted}}>{stateLabels[undo.lifecycle]}로 변경했습니다.</Text>{action('문서 상태 되돌리기',async()=>{await change({kind:r.kind,id:r.id,revision:undo.revision,state_version:undo.state_version,from_state:undo.lifecycle,to_state:undo.previous.lifecycle,reason:undo.previous.reason,replacement:undo.previous.replacement});setUndo(null);setHistory(null);})}{action('알림 닫기',async()=>setUndo(null))}</View>:null}
  {error?<Text accessibilityLiveRegion="polite" style={{color}}>{error}</Text>:null}
 </View>;
}
