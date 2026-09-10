import { tint } from "./core.visual";
import React from "react";
import type { PluginTheme } from "@getpaseo/plugin";
import { MarkdownField } from "./records.document";
import { Pressable, Text, View } from "react-native";

const fields: Record<string,string> = {
  intent:"목표", success_definition:"완료 기준", question:"결정할 내용", rationale:"근거",
  risk_summary:"위험과 영향", statement:"요구사항", design_body:"설계", scope_description:"범위",
  alternatives_body:"검토한 대안", rollback_body:"복구 방법", instruction_body:"작업 내용",
  completion_definition:"완료 기준", summary:"검증 결과 설명", method:"검증 방법",
  surface:"검증 대상", result:"검증 결과", provenance:"기록 출처", observed_at:"확인 시점",
};
const groups: Record<string,string> = { options:"선택지", criteria:"인수 기준", checks:"검증 항목", items:"설계 항목" };
const childFields: Record<string,string> = {
  label:"선택지", title:"제목", description:"설명", consequences:"선택에 따른 영향",
  recommended:"추천", required:"필수", given_text:"전제", when_text:"조건", then_text:"기대 결과",
  design_body:"설계 내용", verification_body:"검증 방법", surface:"검증 대상",
};
/** Native fields are rendered as UI elements; no Markdown assembly or source fallback. */
export function RecordFields({ record, theme, choice, onChoose, disabled = false }: { record:any; theme:PluginTheme; choice?:string; onChoose?:(option:string)=>void; disabled?:boolean }) {
  const color=theme.colors.foreground, muted=theme.colors.foregroundMuted;
  const entry = (key:string,label:string,value:any) => value === null || value === undefined || value === "" ? null :
    <View key={key} style={{gap:10,paddingVertical:4}}>
      <Text style={{color:muted,fontSize:13}}>{label}</Text>
      <MarkdownField theme={theme} text={typeof value === "boolean" || key === "recommended" || key === "required" ? (value ? "예" : "아니요") : String(value)} />
    </View>;
  return <View style={{gap:20}}>
    {Object.entries(fields).map(([key,label]) => entry(key,label,record.fields?.[key]))}
    {Object.entries(groups).map(([group,label]) => record.children?.[group]?.length ? <View key={group} style={{gap:12}}>
      <Text style={{color,fontSize:19,fontWeight:"600"}}>{label}</Text>
      {record.children[group].map((row:any,index:number) => group === "options" && onChoose ?
        <Pressable key={row.option_id} accessibilityRole="radio" accessibilityState={{checked:choice === row.option_id,disabled}} disabled={disabled}
          onPress={() => onChoose(row.option_id)} style={{gap:12,padding:20,borderWidth:1,borderColor:choice === row.option_id ? theme.colors.accent : tint(muted,"28"),borderRadius:14,opacity:disabled ? 0.6 : 1}}>
          <Text style={{color,fontSize:17}}>{choice === row.option_id ? "●" : "○"} {row.label}{row.recommended ? " · 추천" : ""}</Text>
          <MarkdownField text={row.description ?? ""} theme={theme} />
          <MarkdownField text={row.consequences ?? ""} theme={theme} />
        </Pressable> : <View key={Object.entries(row).filter(([key])=>key.endsWith("_id")).sort(([a],[b])=>a.localeCompare(b)).map(([key,value])=>`${key}:${value}`).join("|") || index} style={{gap:12,padding:20,borderWidth:1,borderColor:tint(muted,"28"),borderRadius:14}}>
          {Object.entries(childFields).map(([key,name]) => entry(key,name,row[key]))}
        </View>)}
    </View> : null)}
  </View>;
}
