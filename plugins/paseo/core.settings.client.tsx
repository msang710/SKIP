import React, { useEffect, useRef, useState } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";

const labels = ["현재 대화의 언어로 설명하기", "사용자가 사실을 정정하면 근거를 다시 조사하기", "확인된 사실과 아직 확인할 내용을 구분하기", "검증 가능한 단계로 나누어 구현하기", "나눌 수 없는 변경에는 피해 제한·복구 방법 마련하기", "코드·테스트·실행·화면 확인 결과를 구분하기", "사용자가 요청한 실제 결과로 완료 판단하기", "미실행·부분 검증·남은 문제를 숨기지 않기", "승인받은 작업과 범위 안에서만 실행하기", "관련 없는 사용자 작업과 기록 보존하기"];
type Rule = {id:string;rule:string;status:string;scope:{kind:string;environment_id?:string;operation?:string}};
type Body = {disabled_default_rule_ids:string[];custom_rules:Rule[]};
export function SettingsPanel({theme,projectId,load,save}:{theme:any;projectId:string;load:()=>Promise<any>;save:(payload:any,key:string)=>Promise<any>}) {
  const [body,setBody]=useState<Body|null>(null),[revision,setRevision]=useState(0),[inherited,setInherited]=useState<Body|null>(null);
  const [busy,setBusy]=useState(false),[error,setError]=useState(""),[message,setMessage]=useState("");
  const receipt=useRef<{signature:string;key:string}|null>(null);
  const color=theme.colors.foreground, muted=theme.colors.foregroundMuted;
  const text={color,fontSize:16,lineHeight:24}, field={...text,borderWidth:1,borderColor:muted,borderRadius:8,padding:10};
  async function read(){setBusy(true);setError("");try{const r=await load();if(r.status!=="ok")throw Error(r.error??"설정을 읽지 못했습니다.");const rows=r.data.settings;const own=rows.find((r:any)=>r.id===`project.${projectId}`);setRevision(own?.revision??0);setBody(own?.body??{disabled_default_rule_ids:[],custom_rules:[]});setInherited(rows.find((r:any)=>r.id==='installation')?.body??null);setMessage("");}catch(e){setError(String(e));}finally{setBusy(false);}}
  useEffect(()=>{void read();},[]);
  const button=(title:string,action:()=>void,disabled=false)=><Pressable accessibilityRole="button" accessibilityState={{disabled:busy||disabled}} disabled={busy||disabled} onPress={action} style={{padding:10,borderWidth:1,borderColor:muted,borderRadius:8,opacity:busy||disabled?0.5:1}}><Text style={text}>{title}</Text></Pressable>;
  const update=(id:string,patch:Partial<Rule>)=>{setMessage("");setBody(b=>b&&({...b,custom_rules:b.custom_rules.map(r=>r.id===id?{...r,...patch}:r)}));};
  return <ScrollView style={{flex:1}} contentContainerStyle={{padding:24,gap:16,maxWidth:900,width:"100%",alignSelf:"center"}}>
    <Text style={{...text,fontSize:24,fontWeight:"700"}}>설정</Text>
    <Text style={text}>이 프로젝트에서 에이전트와 협업하는 방식을 정합니다. 저장하면 이 프로젝트의 다음 컨텍스트 조회부터 적용됩니다.</Text>
    {error?<Text accessibilityRole="alert" style={text}>{error}</Text>:null}
    {message?<Text accessibilityLiveRegion="polite" style={text}>{message}</Text>:null}
    {!body?button("다시 불러오기",()=>void read()):<>
    <Text style={{...text,fontWeight:"700"}}>기본 협업 규칙</Text>
    {labels.map((label,index)=>{const id=`C-${String(index+1).padStart(3,'0')}`;const inheritedOff=inherited?.disabled_default_rule_ids.includes(id);const enabled=!body.disabled_default_rule_ids.includes(id)&&!inheritedOff;return <Pressable key={id} accessibilityRole="switch" accessibilityLabel={label} accessibilityState={{checked:enabled,disabled:busy||inheritedOff}} disabled={busy||inheritedOff} onPress={()=>{setMessage("");setBody({...body,disabled_default_rule_ids:enabled?[...body.disabled_default_rule_ids,id]:body.disabled_default_rule_ids.filter(v=>v!==id)});}} style={{paddingVertical:10,flexDirection:"row",gap:12}}><Text style={{color:enabled?theme.colors.accent:muted}}>{enabled?'☑':'☐'}</Text><Text style={{...text,flex:1}}>{label}{inheritedOff?' · 설치 전체에서 꺼짐':''}</Text></Pressable>;})}
    <Text style={{...text,fontWeight:"700"}}>내가 추가한 규칙</Text>
    <Text style={{color:muted}}>예: “기록과 설명은 한국어로 작성해 주세요.”</Text>
    {body.custom_rules.map(r=><View key={r.id} style={{gap:10,padding:12,borderWidth:1,borderColor:muted,borderRadius:8}}>
      <TextInput accessibilityLabel="사용자 규칙 내용" editable={!busy} multiline maxLength={8192} value={r.rule} onChangeText={rule=>update(r.id,{rule})} style={field}/>
      <View style={{flexDirection:"row",gap:8,flexWrap:"wrap"}}>{button(r.status==='active'?'사용 중 · 끄기':'꺼짐 · 켜기',()=>update(r.id,{status:r.status==='active'?'disabled':'active'}))}{button("규칙 삭제",()=>{setMessage("");setBody({...body,custom_rules:body.custom_rules.filter(v=>v.id!==r.id)});})}</View>
      <Text style={{color:muted}}>적용 범위</Text>
      <View style={{flexDirection:"row",gap:8,flexWrap:"wrap"}}>{button(`${r.scope.kind==='project'?'● ':''}프로젝트 전체`,()=>update(r.id,{scope:{kind:'project'}}))}{button(`${r.scope.kind==='environment-operation'?'● ':''}특정 환경·작업`,()=>update(r.id,{scope:{kind:'environment-operation',environment_id:'',operation:'implement'}}))}</View>
      {r.scope.kind==='environment-operation'?<><TextInput accessibilityLabel="규칙 적용 환경 이름" placeholder="기존 규칙에서 사용하는 환경 이름" placeholderTextColor={muted} editable={!busy} value={r.scope.environment_id} onChangeText={environment_id=>update(r.id,{scope:{...r.scope,environment_id}})} style={field}/><View style={{flexDirection:"row",gap:8,flexWrap:"wrap"}}>{[['investigate','조사'],['plan','계획'],['implement','구현'],['deploy','배포']].map(([operation,label])=><View key={operation}>{button(`${r.scope.operation===operation?'● ':''}${label}`,()=>update(r.id,{scope:{...r.scope,operation}}))}</View>)}</View></>:null}
    </View>)}
    {button("+ 규칙 추가",()=>{setMessage("");setBody({...body,custom_rules:[...body.custom_rules,{id:`rule-${Date.now()}-${Math.random().toString(36).slice(2,8)}`,rule:'',status:'active',scope:{kind:'project'}}]});},body.custom_rules.length>=128)}
    {inherited?<View style={{gap:8}}><Text style={{...text,fontWeight:"700"}}>설치 전체에서 적용한 규칙</Text><Text style={{color:muted}}>이 연결은 프로젝트 설정만 수정할 수 있습니다. 설치 전체 규칙은 읽기 전용입니다.</Text>{inherited.custom_rules.map(r=><Text key={r.id} style={text}>{r.status==='active'?'☑':'☐'} {r.rule} · {r.scope.kind==='project'?'전체':`${r.scope.environment_id} / ${r.scope.operation}`}</Text>)}</View>:null}
    <Text style={{color:muted}}>저장은 작업 시작이나 배포 승인이 아닙니다. 규칙이 달라지면 이전 정책을 기준으로 준비된 작업은 재확인이 필요할 수 있습니다.</Text>
    <View style={{flexDirection:"row",gap:8,flexWrap:"wrap"}}>{button("설정 저장",()=>void(async()=>{setBusy(true);setError("");setMessage("");try{const payload={scope:'project',expected_revision:revision,body};const signature=JSON.stringify(payload);if(receipt.current?.signature!==signature)receipt.current={signature,key:`settings-${Date.now()}-${Math.random().toString(36).slice(2)}`};const r=await save(payload,receipt.current.key);if(r.status!=='ok')throw Error(r.code==='STALE'?'다른 곳에서 설정이 변경되었습니다. 내용을 확인한 뒤 저장값 다시 불러오기를 눌러 주세요.':r.error??'저장하지 못했습니다.');setRevision(r.data.revision);receipt.current=null;setMessage('이 프로젝트의 설정을 저장했습니다.');}catch(e){setError(String(e));}finally{setBusy(false);}})(),body.custom_rules.some(r=>!r.rule.trim()||(r.scope.kind==='environment-operation'&&!r.scope.environment_id?.trim())))}{button("저장값 다시 불러오기",()=>void read())}</View>
    </>}
  </ScrollView>;
}
