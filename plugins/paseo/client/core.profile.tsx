import React,{useState,useEffect} from "react";
import {View,Text,TextInput,Pressable} from "react-native";
import {MarkdownField} from "./records.document";

const drafts=new Map<string,{tagline:string;body:string;base:number|null}>();

/** Mounted across navigation: remote refresh never overwrites an editing draft. */
export function ProjectProfile({theme,revision,load,save,draftKey}:{draftKey:string;theme:any;revision:number;load:()=>Promise<any>;save:(op:string,p:any,key:string)=>Promise<any>}) {
 const restored=drafts.get(draftKey);
 const [data,setData]=useState<any>(null),[editing,setEditing]=useState(!!restored),[expanded,setExpanded]=useState(true);
 const [tagline,setTagline]=useState(restored?.tagline??""),[body,setBody]=useState(restored?.body??""),[base,setBase]=useState<number|null>(restored?.base??null);
 const [busy,setBusy]=useState(false),[error,setError]=useState("");
 const color=theme.colors.foreground,muted=theme.colors.foregroundMuted;
 useEffect(()=>{let active=true;load().then(r=>{if(active)setData(r.data);}).catch(e=>{if(active)setError(String(e.message));});return()=>{active=false;};},[revision]);
 useEffect(()=>{if(editing)drafts.set(draftKey,{tagline,body,base});else drafts.delete(draftKey);},[draftKey,editing,tagline,body,base]);
 const reload=async()=>{const r=await load();setData(r.data);return r.data;};
 const action=(label:string,fn:()=>void)=><Pressable accessibilityRole="button" accessibilityLabel={label} disabled={busy} onPress={fn} style={{paddingVertical:6,paddingRight:14}}><Text style={{color:theme.colors.accent,opacity:busy?.5:1}}>{label}</Text></Pressable>;
 const edit=(profile:any=data?.profile)=>{setTagline(profile?.tagline??"");setBody(profile?.body_markdown??"");setBase(data?.metadata.revision??null);setEditing(true);setError("");};
 const send=async(op:string,p:any)=>{setBusy(true);setError("");try{await save(op,p,`profile-${Date.now()}-${Math.random().toString(36).slice(2)}`);await reload();setEditing(false);if(op!=="project.profile.reject")setExpanded(true);}catch(e:any){setError(e.message);await reload().catch(()=>{});}finally{setBusy(false);}};
 const profile=data?.profile;
 return <View style={{gap:8}}>
  {error?<Text accessibilityRole="alert" style={{color:muted}}>{error}</Text>:null}
  {!data?null:editing?<View style={{gap:8}}>
   <TextInput accessibilityLabel="프로젝트 한 줄 소개" placeholder="한 줄 소개" placeholderTextColor={muted} maxLength={256} value={tagline} onChangeText={setTagline} style={{color,borderWidth:1,borderColor:muted,padding:8}}/>
   <TextInput accessibilityLabel="프로젝트 소개 본문" placeholder="목적, 대상, 방향을 자유롭게 작성하세요. Markdown을 사용할 수 있습니다." placeholderTextColor={muted} multiline value={body} onChangeText={setBody} style={{color,minHeight:140,textAlignVertical:"top",borderWidth:1,borderColor:muted,padding:8}}/>
   {base!==data.metadata.revision?<View style={{gap:6}}><Text style={{color:muted}}>소개가 변경되었습니다. 입력은 보존했습니다. 최신 내용과 비교한 뒤 저장하세요.</Text><MarkdownField text={profile?.tagline??""} theme={theme}/><MarkdownField text={profile?.body_markdown??""} theme={theme}/>{action("비교 완료 · 최신 버전에 적용",()=>setBase(data.metadata.revision))}</View>:null}
   <View style={{flexDirection:"row"}}>{base===data.metadata.revision?action("소개 저장",()=>void send("project.profile.save",{expected_revision:base,tagline,body_markdown:body})):null}{action("편집 취소",()=>setEditing(false))}</View>
  </View>:<>
   {profile?<><Text style={{color,fontWeight:"600",fontSize:16}}>{profile.tagline}</Text>{expanded?<MarkdownField text={profile.body_markdown} theme={theme}/>:null}<View style={{flexDirection:"row"}}>{profile.body_markdown.length>0?action(expanded?"소개 접기":"소개 펼치기",()=>setExpanded(!expanded)):null}{action("소개 편집",()=>edit())}</View></>:action("프로젝트 소개 작성",()=>edit())}
   {(data.proposals??[]).map((p:any)=><View key={p.revision} style={{gap:6,borderTopWidth:1,borderColor:muted,paddingTop:8}}>
    <Text style={{color:muted}}>소개 변경안 · {p.revision}</Text>
    {profile?<><Text style={{color:muted}}>현재</Text><MarkdownField text={profile.tagline+"\n\n"+profile.body_markdown} theme={theme}/></>:null}
    <Text style={{color:muted}}>제안</Text><MarkdownField text={p.tagline+"\n\n"+p.body_markdown} theme={theme}/>
    <View style={{flexDirection:"row",flexWrap:"wrap"}}>{p.base_revision===data.metadata.revision?action("변경안 적용",()=>void send("project.profile.accept",{revision:p.revision,digest:p.content_digest,expected_revision:data.metadata.revision})):null}{action("변경안 수정",()=>edit(p))}{action("변경안 거절",()=>void send("project.profile.reject",{revision:p.revision,digest:p.content_digest,expected_revision:data.metadata.revision}))}</View>
   </View>)}
   {data.proposals_more?<Text style={{color:muted}}>최근 변경안 20개를 표시합니다.</Text>:null}
  </>}
 </View>;
}
