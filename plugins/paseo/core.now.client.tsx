import { Badge, Card, tint } from "./core.visual";
import React, { useState } from "react";
import { Pressable, Text, View } from "react-native";
import { MarkdownField } from "./records.document";
import { nowOverview } from "./core.overview";

export function NowPanel({status,theme,open}:{status:any;theme:any;open:(record:any)=>Promise<void>}) {
  const [showPrevious,setShowPrevious]=useState(false);
  const data=nowOverview(status), color=theme.colors.foreground, muted=theme.colors.foregroundMuted;
  const heading={color,fontSize:20,fontWeight:"600" as const};
  const evidence=(id:string)=><Pressable accessibilityRole="button" onPress={()=>void open({kind:'evidence',id,revision:1,title:'확인 근거'})} style={{paddingVertical:8}}><Text style={{color:theme.colors.accent}}>확인 근거 보기 →</Text></Pressable>;
  const fact=(f:any)=><View key={f.id} style={{gap:12,padding:20,borderRadius:16,borderWidth:1,borderColor:tint(muted,"28")}}><MarkdownField text={f.statement} theme={theme}/><Text style={{color:muted}}>{f.created_at} · {f.provenance==='agent_report'?'에이전트 보고':'관측 기록'} · {f.origin?'이관 당시 기록':f.freshness==='current'?'기록에 연결된 소스 일치':'현재 소스 재확인 필요'}</Text>{evidence(f.evidence_id)}</View>;
  return <View style={{gap:18}}>
    <Text style={heading}>현재 상태</Text>
    <Text style={{color:muted}}>근거와 연결된 현재 상태입니다. 실행 중인 환경의 실시간 감시는 아닙니다.</Text>
    {data.facts.length?data.facts.map(fact):<Text style={{color}}>현재 소스로 확인된 상태 기록이 없습니다. 이전 기록은 아래에서 확인할 수 있습니다.</Text>}
    <Text style={heading}>확인</Text>
    {!data.checks.length?<Text style={{color:muted}}>아직 검증 결과가 기록되지 않았습니다.</Text>:null}
    {data.checks.map((c:any)=><View key={c.id} style={{gap:10,padding:18,borderRadius:14,borderWidth:1,borderColor:tint(muted,"28")}}><Text style={{color}}>{c.result} · {c.surface} · {c.freshness==='current'?'기록에 연결된 소스 일치':'재확인 필요'}</Text><MarkdownField text={c.summary} theme={theme}/>{evidence(c.id)}</View>)}
    <Text style={heading}>남은 일</Text>
    {!data.remaining.length?<Text style={{color:muted}}>현재 작업에 연결된 미완료 검증 항목이 없습니다. 전체 작업의 완료를 뜻하지는 않습니다.</Text>:null}
    {data.remaining.map((r:any)=><View key={`${r.work_id}:${r.check_id}`} style={{gap:4}}><Text style={{color}}>{r.state}</Text><MarkdownField text={r.description} theme={theme}/></View>)}
    {status?.work_items_truncated?<Text style={{color:muted}}>일부 작업만 조회되었습니다. 목표별로 남은 확인을 살펴보세요.</Text>:null}
    {data.previousFacts.length?<><Pressable accessibilityRole="button" accessibilityState={{expanded:showPrevious}} onPress={()=>setShowPrevious(v=>!v)} style={{paddingVertical:10}}><Text style={{color:theme.colors.accent}}>{showPrevious?'▾':'▸'} 이전 상태·재확인 필요 ({data.previousFacts.length})</Text></Pressable>{showPrevious?data.previousFacts.map(fact):null}</>:null}
    {(status?.facts?.length??0)>=30?<Text style={{color:muted}}>최근 상태 기록 30개를 조회했습니다. 목표를 선택하면 해당 목표의 기록을 확인할 수 있습니다.</Text>:null}
  </View>;
}
