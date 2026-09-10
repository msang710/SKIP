import React,{useEffect,useRef,useState} from "react";
import {Pressable,ScrollView,Text,View} from "react-native";
import {Action,Badge,Card,EmptyState,Loading,tint} from "./core.visual";
import {MarkdownField} from "./records.document";
const tabs=[['failure','실패 기록'],['guideline','예방 지침'],['claim','검증 범위']] as const;
const labels:Record<string,string>={expected:'기대했던 동작',actual:'실제 발생한 일',conditions:'발생 조건',impact:'영향',cause:'원인',action:'예방 행동',verification:'확인 방법',statement:'검증할 주장',assumptions:'전제 조건',limitations:'보장하지 않는 범위'};
const states:Record<string,string>={investigating:'조사 중',mitigated:'영향 완화',resolved:'사건 해결',active:'유효',retired:'만료',superseded:'대체됨',unknown:'미확인',hypothesis:'가설',confirmed:'근거 확인'};
export function LearningPanel({theme,goal,load,open,revision=0}:{revision?:number;theme:any;goal?:string;load:(query:string,payload:any)=>Promise<any>;open:(r:any)=>Promise<void>}) {
 const [kind,setKind]=useState('failure'),[rows,setRows]=useState<any[]>([]),[cursor,setCursor]=useState<string|null>(null),[expanded,setExpanded]=useState<string|null>(null),[busy,setBusy]=useState(true),[error,setError]=useState('');
 const generation=useRef(0), selection=useRef('');
 async function refresh(append=false){const version=++generation.current;setBusy(true);setError('');try{const r=await load('learning.list',{kind,...(goal?{goal_id:goal}:{}),limit:20,...(append&&cursor?{cursor}:{})});if(version!==generation.current)return;if(r.status!=='ok')throw Error(r.error??'기록 조회 실패');setRows(v=>append?[...v,...r.data.items]:r.data.items);setCursor(r.data.next_cursor);}catch(e){if(version===generation.current)setError(String(e));}finally{if(version===generation.current)setBusy(false);}}
 useEffect(()=>{const key=JSON.stringify([goal,kind]);if(selection.current!==key){selection.current=key;setRows([]);setExpanded(null);}void refresh();return()=>{generation.current++;};},[goal,kind,revision]);
 return <ScrollView style={{flex:1}} contentContainerStyle={{padding:24,gap:18,maxWidth:960,width:'100%',alignSelf:'center'}}>
  <View style={{flexDirection:'row',gap:8,flexWrap:'wrap'}}>{tabs.map(([k,label])=><Pressable key={k} accessibilityRole="button" accessibilityState={{selected:kind===k}} onPress={()=>setKind(k)} style={{padding:12,borderRadius:12,backgroundColor:kind===k?tint(theme.colors.accent,'20'):theme.colors.surface0}}><Text style={{color:kind===k?theme.colors.accent:theme.colors.foregroundMuted,fontWeight:'600'}}>{label}</Text></Pressable>)}<Action theme={theme} label="새로고침" disabled={busy} onPress={()=>void refresh()}/></View>
  {error?<Text accessibilityRole="alert" style={{color:theme.colors.foreground}}>{error}</Text>:null}
  {busy&&!rows.length?<Loading theme={theme}/>:!error&&!rows.length?<EmptyState theme={theme} title="아직 기록된 항목이 없습니다" detail="실패와 검증 근거를 에이전트가 Core에 기록하면 여기에 표시됩니다. 기록이 없다는 것이 실패가 없었다는 뜻은 아닙니다."/>:null}
  {rows.map(row=><Card key={row.id} theme={theme}>
   <View style={{flexDirection:'row',justifyContent:'space-between',gap:8,flexWrap:'wrap'}}><Badge theme={theme} label={states[row.body.state]??(kind==='claim'?'조건부 검증 주장':'기록')}/><Text style={{color:theme.colors.foregroundMuted,fontSize:12}}>v{row.revision} · {kind==='failure'?'실패 기록':row.accepted?'확정 이력 있음':'제안'}</Text></View>
   <Pressable accessibilityRole="button" accessibilityState={{expanded:expanded===row.id}} onPress={()=>setExpanded(expanded===row.id?null:row.id)}><Text style={{color:theme.colors.foreground,fontSize:19,fontWeight:'600',lineHeight:28}}>{row.body.title} {expanded===row.id?'−':'+'}</Text></Pressable>
   <MarkdownField theme={theme} text={row.body.actual??row.body.action??row.body.statement??''}/>
   {kind==='claim'?<Text style={{color:theme.colors.foregroundMuted,lineHeight:21}}>주장 등록만으로 검증된 것은 아닙니다. 현재 소스·환경에 대한 Core 평가를 별도로 확인해야 합니다.</Text>:null}
   {expanded===row.id?<View style={{gap:16}}>
    {Object.entries(labels).filter(([k])=>row.body[k] && k!==(kind==='failure'?'actual':kind==='guideline'?'action':'statement')).map(([k,label])=><View key={k} style={{gap:5}}><Text style={{color:theme.colors.foregroundMuted,fontSize:12,fontWeight:'600'}}>{label}</Text><MarkdownField theme={theme} text={row.body[k]}/></View>)}
    {row.body.cause_state?<Badge theme={theme} label={`원인: ${states[row.body.cause_state]??row.body.cause_state}`}/>:null}
    {kind==='guideline'?<Text style={{color:theme.colors.foregroundMuted}}>지침의 수명과 이 작업에서의 적용·재현 여부는 별도 평가입니다.</Text>:null}
    {(row.occurrences??[]).map((o:any)=><Action key={o.id} theme={theme} label={`발생 근거 · ${o.classification}`} onPress={()=>void open({kind:'evidence',id:o.evidence_id,revision:1,title:'실패 발생 근거'}).catch(e=>setError(String(e)))}/>)}
    {(row.attempts??[]).map((a:any)=><View key={a.id} style={{gap:6}}><MarkdownField theme={theme} text={a.action_body}/><Action theme={theme} label="수정 시도 근거" onPress={()=>void open({kind:'evidence',id:a.evidence_id,revision:1,title:'수정 시도 근거'}).catch(e=>setError(String(e)))}/></View>)}
    {row.history_complete===false?<Text style={{color:theme.colors.foregroundMuted}}>최근 발생·수정 시도 각 30건만 표시했습니다.</Text>:null}
   </View>:null}
  </Card>)}
  {cursor?<Action theme={theme} label="기록 더 보기" disabled={busy} onPress={()=>void refresh(true)}/>:null}
 </ScrollView>;
}
