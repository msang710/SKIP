import { ChangeList, ContinuityScroll } from "./core.motion";
import { reconcile, readWindow } from "./core.continuity";
import { message, reconnectable } from "./core.recovery";
import { LearningPanel } from "./core.learning.client";
import { Action, Badge, Card, Loading, tint } from "./core.visual";
import { recordAttachment, recordCaller } from "./core.attachment";
import { NowPanel } from "./core.now.client";
import { SettingsPanel } from "./core.settings.client";
import { MarkdownField, InlineMarkdown } from "./records.document";
import { decisionSummary, overview, brief } from "./core.overview";
import React, { useEffect, useState, useRef } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useRpc, type PluginAgentPanelProps, type PluginWorkspacePanelProps } from "@getpaseo/plugin";
import { RecordFields } from "./core.record.client";
import { closeCore, connectCore, queryCore, userCore } from "./core.shared";

type Props = PluginAgentPanelProps | PluginWorkspacePanelProps;
type Connection = { sessionId: string; projectId: string; target: string; canStart: boolean };
const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;

export function CorePanel(props: Props) {
  const { theme, layout, workspaceId } = props;
  const agentId = props.context === "agent" ? props.agentId : undefined;
  const connect = useRpc(connectCore), queryRpc = useRpc(queryCore), userRpc = useRpc(userCore), close = useRpc(closeCore);
  const [uiInstanceId] = useState(newId), [connection, setConnection] = useState<Connection | null>(null);
  const [status, setStatus] = useState<any>(null), [inbox, setInbox] = useState<any[]>([]), [risks, setRisks] = useState<any[]>([]);
  const [attachmentNotice, setAttachmentNotice] = useState("");
  const [callerText, setCallerText] = useState("");
  const [inboxCursor, setInboxCursor] = useState<string | null>(null);
  const [goal, setGoal] = useState<string | undefined>();
  const [choice, setChoice] = useState<Record<string, string>>({}), [error, setError] = useState("");
  const [recordRows, setRecordRows] = useState<any[]>([]), [recordCursor, setRecordCursor] = useState<string | null>(null), [recordSearch, setRecordSearch] = useState("");
  const [panelWidth, setPanelWidth] = useState(0), [mobileDetail, setMobileDetail] = useState(false);
  const [navigationWidth, setNavigationWidth] = useState(300), [resizing, setResizing] = useState(false);
  const resizeStart = useRef({ x: 0, width: 300 });
  const [goals, setGoals] = useState<any[]>([]), [goalCursor, setGoalCursor] = useState<string | null>(null);
  const [showProjectOverview, setShowProjectOverview] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [settingsVisited,setSettingsVisited]=useState(false);
  const [learningVisited,setLearningVisited]=useState(false);
  useEffect(()=>{if(showSettings)setSettingsVisited(true);},[showSettings]);
  const [showRecords, setShowRecords] = useState(false);
  const [showLearning, setShowLearning] = useState(false);
  useEffect(()=>{if(showLearning)setLearningVisited(true);},[showLearning]);
  const [recordKind, setRecordKind] = useState<string | undefined>();
  const [selectedRecord, setSelectedRecord] = useState<any>(null);
  const [updatedRecord,setUpdatedRecord]=useState<any>(null);
  const interactionUntil=useRef(0);
  const scrollMemory=useRef<Record<string,number>>({});
  const recordTrail = useRef<any[]>([]);
  const [actionLabel,setActionLabel]=useState<string|null>(null);
  const [busy, setBusy] = useState(false), [details, setDetails] = useState(false), [last, setLast] = useState<any>(null);
  const binding = { uiInstanceId, workspaceId, agentId };
  const pendingKeys = useRef(new Map<string, string>());
  const generation = useRef(0);
  const routeKey = JSON.stringify([props.host.id, workspaceId, agentId]);
  const route = useRef(routeKey); route.current = routeKey;
  function currentRoute() { if (route.current !== routeKey) throw new Error("작업 공간이 변경되었습니다."); }
  const liveConnection = useRef<Connection | null>(null);
  const reconnecting = useRef<Promise<Connection> | null>(null);
  const observedSequence = useRef<number | null>(null);
  async function reconnect() {
    currentRoute();
    if (reconnecting.current) return reconnecting.current;
    const expected = generation.current;
    const old = liveConnection.current;
    const pending = connect(binding).then(c => {
      if (expected !== generation.current || (old && old.projectId !== c.projectId)) {
        void close({ ...binding, sessionId: c.sessionId }).catch(() => {});
        throw new Error("작업 공간이 변경되었습니다.");
      }
      liveConnection.current = c; setConnection(c); return c;
    });
    reconnecting.current = pending;
    try { return await pending; } finally { if (reconnecting.current === pending) reconnecting.current = null; }
  }
  async function query(input: any): Promise<any> {
    currentRoute();
    let c = liveConnection.current;
    const attemptedSession = c?.sessionId ?? input.sessionId;
    let value = await queryRpc({ ...input, sessionId: c?.sessionId ?? input.sessionId }).catch(() => { throw new Error(message("UNAVAILABLE")); });
    currentRoute();
    if (reconnectable((value as any).code)) {
      c = liveConnection.current && liveConnection.current.sessionId !== attemptedSession ? liveConnection.current : await reconnect();
      value = await queryRpc({ ...input, sessionId: c.sessionId }).catch(() => { throw new Error(message("UNAVAILABLE")); });
      currentRoute();
    }
    if ((value as any).status === "error" && (value as any).code !== "NOT_INITIALIZED")
      throw Object.assign(new Error(message(String((value as any).code))),{code:(value as any).code});
    return value;
  }
  async function user(input: any): Promise<any> {
    currentRoute();
    const value:any = await userRpc({ ...input, sessionId: liveConnection.current?.sessionId ?? input.sessionId }).catch(() => { throw new Error(message("UNAVAILABLE")); });
    currentRoute();
    if (value.status === "error") {
      if (reconnectable(value.code)) await reconnect();
      if (reconnectable(value.code) || value.code === "STALE" || value.code === "CONFLICT") await refresh(liveConnection.current, goal, true);
      // Never replay a mutation or uncertain delivery after refreshing.
      throw new Error(message(value.code));
    }
    return value;
  }
  const wide = panelWidth >= 760;
  const maximumNavigationWidth = Math.max(200, Math.min(600, panelWidth - 372));
  const visibleNavigationWidth = Math.max(200, Math.min(navigationWidth, maximumNavigationWidth));
  const resizeNavigation = (value: number) => setNavigationWidth(Math.max(200, Math.min(value, maximumNavigationWidth)));
  const color = theme.colors.foreground, muted = theme.colors.foregroundMuted;
  const textStyle = { color, fontSize: 16, lineHeight: 25 };
  const button = (label: string, action: () => Promise<void>, disabled = false) => <Action label={busy&&actionLabel===label?"처리 중…":label} theme={theme} disabled={disabled || busy} onPress={() => {setActionLabel(label);void run(action);}} />;
  async function run(action: () => Promise<void>) { setBusy(true); setError(""); try { await action(); } catch (e) { setError(e instanceof Error ? e.message : "요청을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요."); } finally { setBusy(false);setActionLabel(null); } }
  async function refresh(c = connection, g: string | null | undefined = goal, preserve = false, changes?:any) {
    if (!c) return;
    const expected = generation.current, bound={...binding,sessionId:c.sessionId};
    const load=(name:any,payload:any)=>query({...bound,query:name,payload});
    const selective=preserve&&changes?.complete&&!changes.resync_required&&changes.events?.length&&changes.events.every((e:any)=>["authoring.submit","authoring.amend","record.propose_revision"].includes(e.kind));
    const touched:any[]=selective?changes.events.flatMap((e:any)=>e.records):[];
    const dirty=(kind?:string)=>!selective||touched.some(r=>!kind||r.kind===kind);
    const cached=(items:any[],cursor:string|null)=>Promise.resolve({items,cursor,sequence:changes.sequence});
    const initial=await load("status",g?{goal_id:g}:{limit:100});
    if(expected!==generation.current)return;
    if(initial.status!=="ok"){if(initial.code==="NOT_INITIALIZED"){setStatus(null);return;}throw Error("기록 조회 실패");}
    // Collect the whole projection before committing any UI state.
    const [s,all,recordsPage,inboxPage,risk] = await Promise.all([
      Promise.resolve(initial),
      dirty("goal")?readWindow(p=>load("status",p),{},"goals",Math.max(100,preserve?goals.length:0)):cached(goals,goalCursor),
      dirty(recordKind)?readWindow(p=>load("record.list",p),{...(g?{goal_id:g}:{}),...(preserve&&recordKind?{kind:recordKind}:{}),...(preserve&&recordSearch?{search:recordSearch}:{})},"items",Math.max(30,preserve?recordRows.length:0)):cached(recordRows,recordCursor),
      dirty("decision")?readWindow(p=>load("inbox",p),g?{goal_id:g}:{},"items",Math.max(30,preserve?inbox.length:0)):cached(inbox,inboxCursor),
      g?load("risks",{goal_id:g}):Promise.resolve(null)
    ]);
    if(expected!==generation.current)return;
    let latest:any=null;
    if(preserve&&selectedRecord&&(!selective||touched.some(r=>r.kind===selectedRecord.kind&&r.id===selectedRecord.id))){
      const r=await load("record",{kind:selectedRecord.kind,id:selectedRecord.id});latest=r.data;
      if(expected!==generation.current)return;
    }
    setError("");
    setGoals(old=>reconcile(old,all.items));setGoalCursor(all.cursor);
    setRecordRows(old=>reconcile(old,recordsPage.items));setRecordCursor(recordsPage.cursor);
    setInbox(old=>reconcile(old,inboxPage.items));setInboxCursor(inboxPage.cursor);
    setStatus(s.data);setRisks(risk?.data.assessments??[]);
    if(!preserve){setShowRecords(false);recordTrail.current=[];setSelectedRecord(null);setUpdatedRecord(null);setRecordSearch("");setRecordKind(undefined);setChoice({});}
    else if(latest){
      const next={...latest,title:latest.fields?.title??latest.fields?.question??selectedRecord.title};
      if(latest.revision!==selectedRecord.revision) {
        setUpdatedRecord(next);
        setSelectedRecord((old:any)=>({...old,current_revision:latest.current_revision??latest.revision}));
      }
      else setSelectedRecord((old:any)=>JSON.stringify(old)===JSON.stringify(next)?old:next);
    }
    observedSequence.current=Math.min(s.sequence,all.sequence!,recordsPage.sequence!,inboxPage.sequence!,risk?.sequence??s.sequence);
  }
  useEffect(() => {
    generation.current += 1; scrollMemory.current={}; pendingKeys.current.clear(); liveConnection.current = null; observedSequence.current = null; reconnecting.current = null;
    let gone = false, current: Connection | null = null;
    setShowRecords(false);
    setAttachmentNotice(""); setInboxCursor(null);
    setSettingsVisited(false);setLearningVisited(false);setShowProjectOverview(false); setShowLearning(false); setShowSettings(false); setConnection(null); setStatus(null); setGoals([]); setRecordRows([]); setRecordCursor(null); setGoalCursor(null); setMobileDetail(false); setInbox([]); setGoal(undefined); setLast(null); recordTrail.current = []; setSelectedRecord(null);
    void connect(binding).then(async c => {
      current = c;
      if (gone) { await close({ ...binding, sessionId: c.sessionId }); return; }
      liveConnection.current = c; setConnection(c);
      try { await refresh(c, null); } catch (e) { if (!gone) setError(e instanceof Error ? e.message : String(e)); }
    }).catch(e => { if (!gone) setError(message("UNAVAILABLE")); });
    return () => { generation.current += 1; gone = true; if (liveConnection.current ?? current) void close({ ...binding, sessionId: (liveConnection.current ?? current)!.sessionId }).catch(() => {}); };
  }, [workspaceId, agentId, props.host.id]);
  useEffect(() => {
    if (!connection) return;
    let stopped = false, running = false;
    const timer = setInterval(() => {
      if (running || busy || stopped || Date.now()<interactionUntil.current) return;
      running = true;
      void query({...binding,sessionId:connection.sessionId,query:"changes",payload:{...(observedSequence.current!==null?{since:observedSequence.current}:{})}}).then(async r => {
        if (!stopped && r.status === "ok") {
          setError(previous => previous === "최신 상태를 확인하지 못했습니다. 연결되면 다시 갱신합니다." ? "" : previous);
          if (r.sequence !== observedSequence.current) await refresh(liveConnection.current, goal, true, r.data);
        }
      }).catch(() => { if (!stopped) setError("최신 상태를 확인하지 못했습니다. 연결되면 다시 갱신합니다."); }).finally(() => { running = false; });
    }, 5000);
    return () => { stopped = true; clearInterval(timer); };
  }, [connection, goal, busy, selectedRecord, recordKind, recordSearch, workspaceId, agentId, props.host.id]);
  async function submit(command: "project.activate" | "decision.select" | "execution.prepare" | "execution.cancel" | "settings.update", payload: Record<string, unknown>) {
    if (!connection) return;
    const signature = JSON.stringify({ command, payload });
    const key = pendingKeys.current.get(signature) ?? newId(); pendingKeys.current.set(signature, key);
    const value = await user({ ...binding, sessionId: connection.sessionId, command, payload, key });
    setLast(value); await refresh(liveConnection.current,goal,true); pendingKeys.current.delete(signature); return value as any;
  }
  async function readRecords(append = false, filter: string | null | undefined = recordKind) {
    generation.current += 1;
    const expected = generation.current;
    const response = await query({ ...binding, sessionId: connection!.sessionId, query: "record.list", payload: {
      ...(filter ? { kind: filter } : {}), ...(goal ? { goal_id: goal } : {}), ...(recordSearch ? { search: recordSearch } : {}), ...(append && recordCursor ? { cursor: recordCursor } : {}), limit: 30,
    } });
    if (expected !== generation.current) return;
    const data = (response as any).data;
    setShowLearning(false); setShowSettings(false); setShowRecords(true); setMobileDetail(true);
    setRecordRows(previous => append ? [...previous, ...data.items] : data.items); setRecordCursor(data.next_cursor); recordTrail.current = []; setSelectedRecord(null);
  }
  async function execute(work: any, selection?: any) {
    const change = risks.find(r => r.kind === "change" && r.freshness === "current");
    const goalRisk = risks.find(r => r.kind === "goal" && r.scope_id === change?.scope_id && r.snapshot_id === change?.snapshot_id && r.freshness === "current");
    if (!change || !goalRisk) throw new Error("현재 소스의 위험 평가가 필요합니다. 에이전트에게 조사를 요청하세요.");
    await submit("execution.prepare", { work_id: work.id, revision: work.revision, goal_risk_id: goalRisk.id, change_risk_id: change.id, ...(selection ? { selection } : {}) });
  }
  const workItems = (status?.work_items ?? []).filter((w: any) => w.lifecycle === "active");
  const nextWork = workItems.length === 1 ? workItems[0] : null;
  const selectedGoal = goals.find(g => g.id === goal);
  const activeRecordKind = showRecords ? recordKind : undefined;
  const summary = overview(status, inbox, goals);
  async function selectGoal(id?: string) {
    generation.current += 1;
    setShowLearning(false); setShowSettings(false);
    setGoal(id); setRecordKind(undefined); setRecordSearch(""); setShowRecords(false); recordTrail.current = []; setSelectedRecord(null); setRecordRows([]); setMobileDetail(true);
    await refresh(connection, id ?? null);
  }
  async function openDocument(document: any) {
    generation.current += 1;
    const expected = generation.current;
    const r = await query({ ...binding, sessionId: connection!.sessionId, query: "record", payload: { kind: document.kind, id: document.id, revision: document.revision } });
    if (expected !== generation.current) return;
    if ((r as any).status !== "ok") throw new Error((r as any).error ?? "기록을 조회하지 못했습니다.");
    const data = (r as any).data;
    recordTrail.current.push(selectedRecord);
    setAttachmentNotice(""); setCallerText("");
    setUpdatedRecord(null);setSelectedRecord({ ...data, title: data.fields.title ?? data.fields.question ?? document.title });
    setMobileDetail(true);
  }
  const navItem = (title: string, selected: boolean, action: () => Promise<void>, subtitle?: string) =>
    <Pressable accessibilityRole="button" accessibilityState={{ selected, disabled: busy }} disabled={busy} onPress={() => void run(action)}
      style={({pressed})=>({ padding: 14, gap: 5, marginVertical:2, borderRadius:12, borderLeftWidth: 3, borderLeftColor: selected ? theme.colors.accent : "transparent", backgroundColor: selected || pressed ? tint(theme.colors.accent,"16") : "transparent", opacity: busy ? 0.6 : 1 })}>
      <Text style={{ color: selected ? theme.colors.accent : color, fontWeight: selected ? "700" : "400", lineHeight: 22 }}><InlineMarkdown text={title} theme={theme} /></Text>
      {subtitle ? <Text numberOfLines={2} style={{ color: muted, fontSize: 12 }}>{subtitle}</Text> : null}
    </Pressable>;
  return <View onTouchStart={()=>{interactionUntil.current=Date.now()+800;}} onLayout={event => setPanelWidth(event.nativeEvent.layout.width)} style={{ flex: 1, minHeight: 0, backgroundColor: theme.colors.surface0 }}>
    {error || !wide ? <View style={{ padding: 16, gap: 6, borderBottomWidth: 1, borderColor: muted }}>
      {error ? <Text accessibilityRole="alert" style={textStyle}>{error}</Text> : null}
      {!wide ? button(mobileDetail ? "← 목표·기록 목록" : "선택한 목표 상세 →", async () => setMobileDetail(!mobileDetail)) : null}
    </View> : null}
    <View style={{ flex: 1, minHeight: 0, flexDirection: "row" }}>
      {wide || !mobileDetail ? <View accessibilityLabel="NOW와 목표 목록" style={{ width: wide ? visibleNavigationWidth : "100%", flexGrow: 0, flexShrink: 0, minHeight: 0, borderRightWidth: 0, borderColor: muted }}>
        <ContinuityScroll memory={scrollMemory} scene="goals" onScrollBeginDrag={()=>{interactionUntil.current=Date.now()+60_000;}} onScrollEndDrag={()=>{interactionUntil.current=Date.now()+600;}} maintainVisibleContentPosition={{minIndexForVisible:0}} style={{ flex: 1 }} contentContainerStyle={{ padding: 12, gap: 8 }}>
        {navItem("NOW", !goal, () => selectGoal())}
        <View style={{flexDirection:"row",justifyContent:"space-between",alignItems:"center",padding:10,marginTop:12}}><Text style={{color:muted,fontSize:12,fontWeight:"700",letterSpacing:1.5}}>목표</Text><Badge theme={theme} label={String(goals.length)+(goalCursor?"+":"")}/></View>
        <ChangeList rows={goals} theme={theme} render={(g,index)=><View key={g.id} style={index < goals.length - 1 ? { borderBottomWidth: 1, borderBottomColor: tint(muted, "22") } : undefined}>{navItem(g.fields.title, goal === g.id, () => selectGoal(g.id))}</View>} />
        {goalCursor ? button("목표 더 보기", async () => {
          const r = await query({ ...binding, sessionId: connection!.sessionId, query: "status", payload: { cursor: goalCursor, limit: 100 } });
          setGoals(previous => [...previous, ...(r as any).data.goals]); setGoalCursor((r as any).data.next_cursor);
        }) : null}
        </ContinuityScroll>
      </View> : null}
      {wide ? <View accessibilityRole="adjustable" accessibilityLabel="좌우 패널 너비 조절"
        accessibilityValue={{min:200,max:maximumNavigationWidth,now:visibleNavigationWidth}}
        accessibilityActions={[{name:"increment",label:"목표 목록 넓히기"},{name:"decrement",label:"목표 목록 좁히기"}]}
        onAccessibilityAction={event => resizeNavigation(visibleNavigationWidth + (event.nativeEvent.actionName === "increment" ? 24 : -24))}
        onStartShouldSetResponder={() => true}
        onResponderGrant={event => { resizeStart.current={x:event.nativeEvent.pageX,width:visibleNavigationWidth};setResizing(true); }}
        onResponderMove={event => resizeNavigation(resizeStart.current.width + event.nativeEvent.pageX - resizeStart.current.x)}
        onResponderRelease={() => setResizing(false)} onResponderTerminate={() => setResizing(false)}
        onResponderTerminationRequest={() => false}
        style={{width:12,flexShrink:0,alignItems:"center",justifyContent:"center",backgroundColor:resizing ? theme.colors.surface0 : undefined,...({cursor:"col-resize",touchAction:"none",userSelect:"none"} as any)}}>
        <View style={{position:"absolute",top:0,bottom:0,width:1,backgroundColor:muted,opacity:0.4}} />
        <View style={{height:36,width:4,borderRadius:2,backgroundColor:resizing ? theme.colors.accent : muted}} />
      </View> : null}
      {wide || mobileDetail ? <View accessibilityLabel="선택한 목표와 기록 상세" style={{ flex: 1, minWidth: 0, minHeight: 0 }}>
        <View accessibilityLabel="기록 탐색 도구" style={{ flexDirection: "row", flexWrap: "wrap", alignItems: "center", gap: 8, paddingHorizontal: wide ? 24 : 16, paddingVertical: 14, borderBottomWidth: 1, borderColor: tint(muted,"25") }}>
          {button("← 이전으로", async () => {
            if (showSettings) setShowSettings(false);
            else if (selectedRecord) setSelectedRecord(recordTrail.current.pop() ?? null);
            else if (showLearning) setShowLearning(false);
            else if (showRecords) setShowRecords(false);
            else if (goal) await selectGoal();
          }, !showLearning && !showSettings && !selectedRecord && !showRecords && !goal)}
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
          {([[undefined,"전체"],["decision","결정"],["requirement","요구"],["plan","설계"],["work_item","작업"],["evidence","근거·검증"]] as const).map(([kind,label]) =>
            <Pressable key={label} disabled={busy} accessibilityRole="button" accessibilityState={{selected:activeRecordKind === kind}} onPress={() => void run(async () => {
              if (kind === undefined) { await selectGoal(goal); return; }
              setRecordKind(kind); await readRecords(false,kind);
            })} style={{paddingHorizontal:12,paddingVertical:9,borderRadius:9,backgroundColor:!showLearning && activeRecordKind===kind?tint(theme.colors.accent,"18"):"transparent"}}><Text style={{color:(activeRecordKind === kind)?theme.colors.accent:muted}}>{label}</Text></Pressable>)}
        </View>
        <Pressable accessibilityRole="button" accessibilityState={{selected:showLearning}} onPress={()=>{setShowLearning(true);setShowSettings(false);setSelectedRecord(null);setMobileDetail(true);}} style={{padding:10,borderRadius:9,backgroundColor:showLearning?tint(theme.colors.accent,"18"):undefined}}><Text style={{color:showLearning?theme.colors.accent:muted,fontWeight:"600"}}>실패·학습</Text></Pressable>
        <View style={{marginLeft:"auto",flexDirection:"row",alignItems:"center",gap:8,maxWidth:"100%",flexShrink:1}}>
        <Pressable accessibilityRole="button" accessibilityLabel="설정" accessibilityState={{selected:showSettings,disabled:!connection}} disabled={!connection} onPress={()=>{setShowSettings(v=>!v);setMobileDetail(true);}} style={{padding:10}}><Text style={{color:showSettings?theme.colors.accent:color,fontSize:24}}>⚙</Text></Pressable>
        <TextInput accessibilityLabel="기록 검색" placeholder="기록 제목 검색" placeholderTextColor={muted} value={recordSearch}
          onChangeText={value => { setRecordSearch(value); setRecordCursor(null); }} onSubmitEditing={() => void run(() => readRecords())}
          style={{ ...textStyle, width: wide ? 240 : 180, flexShrink: 1, borderWidth: 1, borderColor: tint(muted,"30"), borderRadius: 12, padding: 10 }} />
        {button("기록 검색", () => readRecords(), !connection)}
        </View>
        </View>
        {connection && settingsVisited ? <View style={{flex:showSettings?1:0,display:showSettings?"flex":"none"}}><SettingsPanel key={routeKey} theme={theme} projectId={connection.projectId} load={()=>query({...binding,sessionId:connection.sessionId,query:"settings",payload:{}})} save={(payload,key)=>user({...binding,sessionId:connection.sessionId,command:"settings.update",payload,key})} /></View>:null}
        {connection && learningVisited ? <View style={{flex:showLearning&&!showSettings&&!selectedRecord?1:0,display:showLearning&&!showSettings&&!selectedRecord?"flex":"none"}}><LearningPanel revision={observedSequence.current ?? 0} key={`${routeKey}:${goal??"all"}`} theme={theme} goal={goal} load={(name,payload)=>query({...binding,sessionId:connection.sessionId,query:name as any,payload})} open={r=>run(()=>openDocument(r))}/></View>:null}
        {showSettings || (showLearning && !selectedRecord) ? null : selectedRecord ? <ContinuityScroll memory={scrollMemory} scene={selectedRecord? `record:${selectedRecord.kind}:${selectedRecord.id}`:showRecords?`list:${goal??"all"}:${recordKind??"all"}:${recordSearch}`:`overview:${goal??"all"}`} onScrollBeginDrag={()=>{interactionUntil.current=Date.now()+60_000;}} onScrollEndDrag={()=>{interactionUntil.current=Date.now()+600;}} maintainVisibleContentPosition={{minIndexForVisible:0}} style={{ flex: 1 }} contentContainerStyle={{ padding: wide ? 24 : 16, gap: 20 }}>
          {updatedRecord && updatedRecord.id===selectedRecord.id ? <View style={{gap:8}}>
            <Text accessibilityLiveRegion="polite" style={{color:muted}}>이 기록이 수정되었습니다. 읽던 내용은 유지했습니다.</Text>
            {button("변경된 내용 보기",async()=>{setSelectedRecord(updatedRecord);setUpdatedRecord(null);})}
          </View>:null}
          <Text style={{ color: muted }}>{selectedGoal?.fields.title ?? "프로젝트 기록"}</Text>
          <Text style={{ color, fontSize: 24, fontWeight: "700" }}>{selectedRecord.title}</Text>
          <Text style={{ color: muted }}>기록 상태: {selectedRecord.origin?.source_status ?? selectedRecord.lifecycle}</Text>
          {selectedRecord.origin?.unresolved_json && selectedRecord.origin.unresolved_json !== "[]" ? <Text style={{color:muted}}>연결 확인 필요: {JSON.parse(selectedRecord.origin.unresolved_json).join(" · ")}</Text> : null}
          <View style={{flexDirection:"row",flexWrap:"wrap",gap:6}}>
            {Object.entries({decisions:"decision",requirements:"requirement",plan_items:"plan",dependencies:"work_item"}).flatMap(([key,kind]) => (selectedRecord.children?.[key] ?? []).map((link:any,index:number) => {
              const id=link.decision_id ?? link.requirement_id ?? link.plan_id ?? link.depends_on_id;
              const revision=link.decision_revision ?? link.requirement_revision ?? link.plan_revision ?? link.depends_on_revision;
              return <View key={`${key}-${index}`}>{button(link.rationale ?? link.reason ?? "연결된 기록", () => openDocument({id,revision,kind,title:"연결된 기록"}))}</View>;
            }))}
          </View>
          {button(props.addComposerAttachment ? "이 문서를 채팅에 전달" : "SKIP 호출자 복사", async () => {
            if (!connection) return;
            if (!props.addComposerAttachment) {
              const caller=recordCaller(connection.projectId,selectedRecord);
              setCallerText(caller);
              try {
                const clipboard=(globalThis as any).navigator?.clipboard;
                if (!clipboard?.writeText) throw new Error("clipboard unavailable");
                await clipboard.writeText(caller);
                setAttachmentNotice("SKIP 호출자를 복사했습니다. 현재 대화에 붙여넣어 보내세요.");
              } catch {
                setAttachmentNotice("자동 복사를 사용할 수 없습니다. 아래 호출자를 선택해 복사하세요.");
              }
              return;
            }
            const expected=generation.current;
            setAttachmentNotice("");
            const reply=await query({...binding,sessionId:connection.sessionId,query:"record",payload:{kind:selectedRecord.kind,id:selectedRecord.id,revision:selectedRecord.revision}});
            if(expected!==generation.current) return;
            if((reply as any).status!=="ok") throw new Error((reply as any).error ?? "문서를 읽지 못했습니다.");
            await props.addComposerAttachment(recordAttachment(connection.projectId,(reply as any).data,selectedRecord.title));
            if(expected===generation.current) setAttachmentNotice("현재 채팅 작성창에 첨부했습니다. 메시지를 덧붙여 보내세요.");
          }, !connection)}
          {!props.addComposerAttachment ? <Text style={{color:muted}}>이 화면에서는 정확한 문서를 선택하는 SKIP 호출자를 복사해 전달합니다.</Text> : null}
          {callerText ? <TextInput accessibilityLabel="문서 선택 SKIP 호출자" value={callerText} multiline selectTextOnFocus style={{color,borderWidth:1,borderColor:muted,padding:12}} /> : null}
          {attachmentNotice ? <Text accessibilityLiveRegion="polite" style={{color:muted}}>{attachmentNotice}</Text> : null}
          <RecordFields record={selectedRecord} theme={theme}
            choice={choice[`${selectedRecord.id}:${selectedRecord.revision}`] ?? selectedRecord.selection?.option_id}
            disabled={busy || !connection || selectedRecord.current_revision !== selectedRecord.revision}
            onChoose={selectedRecord.kind === "decision" ? option => setChoice(v => ({...v,[`${selectedRecord.id}:${selectedRecord.revision}`]:option})) : undefined} />
          {selectedRecord.kind === "decision" ? <View style={{gap:10}}>
            {selectedRecord.selection ? <Text style={{color:muted}}>저장된 선택: {selectedRecord.children.options.find((o:any)=>o.option_id===selectedRecord.selection.option_id)?.label ?? selectedRecord.selection.option_id}</Text> : null}
            {selectedRecord.current_revision !== selectedRecord.revision ? <Text style={{color:muted}}>이전 버전입니다. 최신 결정에서 선택하세요.</Text> : null}
            {!selectedRecord.children?.options?.length ? <Text style={{color:muted}}>선택지 정리가 필요한 결정입니다.</Text> : button("결정 저장", async () => {
              if (!connection) return;
              const record = selectedRecord, expected = generation.current;
              const payload = {decision_id:record.id,revision:record.revision,option_id:choice[`${record.id}:${record.revision}`] ?? record.selection?.option_id};
              const signature = JSON.stringify({command:"decision.select",payload});
              const key = pendingKeys.current.get(signature) ?? newId(); pendingKeys.current.set(signature,key);
              const result:any = await user({...binding,sessionId:connection.sessionId,command:"decision.select",payload,key});
              if (expected !== generation.current) return;
              if (result.status !== "ok") throw new Error(result.error ?? "결정을 저장하지 못했습니다.");
              pendingKeys.current.delete(signature);
              const fresh:any = await query({...binding,sessionId:connection.sessionId,query:"record",payload:{kind:"decision",id:record.id}});
              if (expected !== generation.current) return;
              if (fresh.status !== "ok") throw new Error("결정은 저장됐지만 재조회하지 못했습니다. 다시 열어 확인하세요.");
              setChoice(v => {const next={...v};delete next[`${record.id}:${record.revision}`];return next;});
              setSelectedRecord({...fresh.data,title:fresh.data.fields.question});
              setRecordRows(rows => rows.map(row => row.id === fresh.data.id ? {...row,revision:fresh.data.revision,selection_state:fresh.data.selection_state,selection_stale:fresh.data.selection_stale,selected_option:fresh.data.selected_option,action_state:fresh.data.action_state} : row));
            }, !connection || selectedRecord.current_revision !== selectedRecord.revision || !(choice[`${selectedRecord.id}:${selectedRecord.revision}`] ?? selectedRecord.selection?.option_id))}
          </View> : null}
        </ContinuityScroll> : showRecords ? <ContinuityScroll memory={scrollMemory} scene={selectedRecord? `record:${selectedRecord.kind}:${selectedRecord.id}`:showRecords?`list:${goal??"all"}:${recordKind??"all"}:${recordSearch}`:`overview:${goal??"all"}`} onScrollBeginDrag={()=>{interactionUntil.current=Date.now()+60_000;}} onScrollEndDrag={()=>{interactionUntil.current=Date.now()+600;}} maintainVisibleContentPosition={{minIndexForVisible:0}} style={{ flex: 1 }} contentContainerStyle={{ padding: wide ? 24 : 16, gap: 8 }}>
          <Text style={{color,fontSize:20,fontWeight:"600"}}>{selectedGoal?.fields.title ?? "프로젝트 전체"} · 기록</Text>
        <ChangeList rows={recordRows} theme={theme} render={(document,index)=><View key={document.id} style={index < recordRows.length - 1 ? { borderBottomWidth: 1, borderBottomColor: tint(muted, "22") } : undefined}>{navItem(document.title, selectedRecord?.id === document.id, () => openDocument(document), document.kind === "decision" ? decisionSummary(document) : document.origin ? `${document.origin.source_key} · ${document.origin.source_status}` : document.kind)}</View>} />
        {!recordRows.length ? <Text style={{ color: muted, padding: 8 }}>표시할 기록이 없습니다.</Text> : null}
        {recordCursor ? button("기록 더 보기", () => readRecords(true)) : null}
        </ContinuityScroll> : <ContinuityScroll memory={scrollMemory} scene={selectedRecord? `record:${selectedRecord.kind}:${selectedRecord.id}`:showRecords?`list:${goal??"all"}:${recordKind??"all"}:${recordSearch}`:`overview:${goal??"all"}`} onScrollBeginDrag={()=>{interactionUntil.current=Date.now()+60_000;}} onScrollEndDrag={()=>{interactionUntil.current=Date.now()+600;}} maintainVisibleContentPosition={{minIndexForVisible:0}} style={{ flex: 1 }} contentContainerStyle={{ padding: wide ? 28 : 16, gap: 18, maxWidth: 900, width: "100%", alignSelf: "center" }}>
          <View style={{gap:10,paddingVertical:12}}><Text style={{color,fontSize:32,lineHeight:42,fontWeight:"700",letterSpacing:-1}}>{selectedGoal?.fields.title ?? "NOW"}</Text></View>
          {!connection?<Loading theme={theme}/>:null}
          {status && !goal?<View style={{flexDirection:"row",flexWrap:"wrap",gap:10}}>{[["결정 대기",summary.decisions.length],["조회된 작업",summary.work.length],["최근 검증",summary.checks.length]].map(([label,value])=><View key={label} style={{flexGrow:1,flexBasis:140,padding:18,borderRadius:14,borderWidth:1,borderColor:tint(muted,"28"),gap:6}}><Text style={{color:muted,fontSize:12}}>{label}</Text><Text style={{color,fontSize:28,fontWeight:"700"}}>{value}</Text></View>)}</View>:null}
          {connection && !status ? button("이 프로젝트에서 사용", async () => { await submit("project.activate", { name: "현재 프로젝트" }); }) : null}
          {status ? <>
      {!goal ? <>
        <NowPanel status={status} theme={theme} open={record=>run(()=>openDocument(record))} />
        {button(showProjectOverview ? "프로젝트 목표·작업 목록 접기" : "프로젝트 목표·작업 목록 펼치기",async()=>setShowProjectOverview(v=>!v))}
      </> : null}
      {goal || showProjectOverview ? <>
      {selectedGoal ? <View style={{gap:8}}><Text style={{color,fontSize:18,fontWeight:"600"}}>목표</Text><MarkdownField text={selectedGoal.fields.intent} theme={theme} /><Text style={{color:muted}}>완료 기준</Text><MarkdownField text={selectedGoal.fields.success_definition} theme={theme} /></View> : null}
      {!goal ? <View style={{ gap: 12 }}>
        <Text style={{ color, fontSize: 20, fontWeight: "600" }}>진행 중인 목표</Text>
        {summary.empty ? <Text style={textStyle}>아직 요청으로 시작한 목표가 없습니다. 현재 대화에서 원하는 작업을 요청하면 목표를 만들 수 있습니다.</Text> : null}
        {summary.goals.slice(0, 8).map((g: any) => <View key={g.id}>{button(g.fields.title, () => selectGoal(g.id))}</View>)}
        {summary.goals.length > 8 || goalCursor ? <Text style={{ color: muted }}>더 많은 목표는 왼쪽 목표 목록에서 선택하세요.</Text> : null}
      </View> : null}
      <Text style={{ color, fontSize: 20, fontWeight: "600" }}>결정이 필요한 일</Text>
      {!summary.decisions.length ? <Text style={{ color: muted }}>현재 조회된 기록에 결정 대기 항목이 없습니다.</Text> : null}
      <ChangeList rows={summary.decisions} theme={theme} render={card=><View key={card.id} style={{ padding: 22, gap: 16, borderWidth: 1, borderColor: tint(theme.colors.accent,"50"), borderRadius: 18 }}>
        <Text style={{ ...textStyle, fontWeight: "600", fontSize: 19 }}><InlineMarkdown text={card.fields.question} theme={theme} /></Text>
        {card.children.options.map((option: any) => <Pressable key={option.option_id} accessibilityRole="radio" accessibilityState={{ checked: choice[`${card.id}:${card.revision}`] === option.option_id }}
          onPress={() => setChoice(v => ({ ...v, [`${card.id}:${card.revision}`]: option.option_id }))} style={{ padding: 12, gap: 4, borderWidth: 1, borderColor: choice[`${card.id}:${card.revision}`]===option.option_id?theme.colors.accent:tint(muted,"30"), backgroundColor:choice[`${card.id}:${card.revision}`]===option.option_id?tint(theme.colors.accent,"16"):undefined, borderRadius: 12 }}>
          <Text style={textStyle}>{choice[`${card.id}:${card.revision}`] === option.option_id ? "●" : "○"} <InlineMarkdown text={option.label} theme={theme} />{option.recommended ? " · 추천" : ""}</Text>
          <MarkdownField text={option.consequences} theme={theme} />
        </Pressable>)}
        <MarkdownField text={card.fields.rationale} theme={theme} /><Text style={{ color: muted }}>위험</Text><MarkdownField text={card.fields.risk_summary} theme={theme} />
        {card.selection ? <Text style={{ color: muted }}>저장된 선택: {card.children.options.find((o: any) => o.option_id === card.selection.option_id)?.label}</Text> : null}
        {card.selection_stale ? <Text style={textStyle}>질문이 변경됐습니다. 다시 확인하세요.</Text> : null}
        {button("선택 저장", async () => { await submit("decision.select", { decision_id: card.id, revision: card.revision, option_id: choice[`${card.id}:${card.revision}`] }); }, !choice[`${card.id}:${card.revision}`])}
        {nextWork && connection?.canStart ? button(`선택 확정하고 ${nextWork.fields.operation === "implement" ? "구현" : nextWork.fields.operation === "design" ? "설계" : "작업 진행"}`,
          () => execute(nextWork, { decision_id: card.id, revision: card.revision, option_id: choice[`${card.id}:${card.revision}`] }), !choice[`${card.id}:${card.revision}`]) : null}
      </View>} />
      {summary.incompleteDecisions.length ? <View style={{gap:10}}>
        <Text style={{color,fontSize:20,fontWeight:"600"}}>선택지 정리가 필요한 기록</Text>
        <Text style={{color:muted}}>선택지가 없어 지금 선택하거나 저장할 수 없습니다. 에이전트가 질문과 선택지를 보완해야 합니다.</Text>
        {summary.incompleteDecisions.map((card:any) => <View key={card.id}>{button(card.fields.question, () => openDocument({kind:"decision",id:card.id,revision:card.revision,title:card.fields.question}))}</View>)}
      </View> : null}
      {inboxCursor ? button("결정 기록 더 보기", async () => {
        const reply=await query({...binding,sessionId:connection!.sessionId,query:"inbox",payload:{...(goal?{goal_id:goal}:{}),cursor:inboxCursor}});
        if ((reply as any).status!=="ok") throw new Error((reply as any).error);
        setInbox(v=>[...v,...(reply as any).data.items]);setInboxCursor((reply as any).data.next_cursor);
      }) : null}
      <Text style={{ color, fontSize: 20, fontWeight: "600" }}>작업과 검증</Text>
      {!summary.work.length ? <Text style={{ color: muted }}>아직 작업 계획이 없습니다. 목표를 조사하고 계획을 기록하면 여기에 표시됩니다.</Text> : null}
      {(goal ? summary.work : summary.work.slice(0, 8)).map((w: any) => <View key={w.id} style={{ gap: 10,padding:18,borderWidth:1,borderColor:tint(muted,"25"),borderRadius:14 }}>
        {button(w.fields.title, () => openDocument({ kind: "work_item", id: w.id, revision: w.revision, title: w.fields.title }))}
        <Text style={{ color: muted }}>{w.displayState}</Text>
        {button(w.fields.operation === "implement" ? "이 작업 구현" : "이 작업 진행", () => execute(w), !connection?.canStart)}
      </View>)}
      {status.work_items_truncated || (!goal && summary.work.length > 8) ? <Text style={{ color: muted }}>일부 작업만 표시했습니다. 목표를 선택해 나머지를 확인하세요.</Text> : null}
      <Text style={{ color, fontSize: 20, fontWeight: "600" }}>최근 검증 기록</Text>
      {!summary.checks.length ? <Text style={{ color: muted }}>아직 새 검증 결과가 기록되지 않았습니다.</Text> : null}
      {summary.checks.slice(0, 5).map((c: any) => <View key={c.id} style={{ gap: 6 }}>
        <Text style={{ color: muted }}>{c.result} · {c.surface} · {c.freshness === "current" ? "현재 소스 기준" : "소스 재확인 필요"}</Text>
        {button(brief(c.summary), () => openDocument({ kind: "evidence", id: c.id, revision: 1, title: "검증 기록" }))}
      </View>)}
      {summary.historicalChecks ? <Text style={{ color: muted }}>이관된 과거 검증은 현재 결과에 합산하지 않습니다. 근거·검증 목록에서 확인할 수 있습니다.</Text> : null}
      {goal && status.remaining.length ? <View style={{ gap: 8 }}>
        <Text style={{ color, fontSize: 20, fontWeight: "600" }}>남은 확인</Text>
        {status.remaining.slice(0, 10).map((r: any) => <Text key={`${r.work_id}:${r.check_id}`} style={textStyle}>{brief(r.description)} · {r.state}</Text>)}
        {status.remaining.length > 10 ? <Text style={{ color: muted }}>일부 확인 항목입니다. 각 작업에서 전체 조건을 확인하세요.</Text> : null}
      </View> : null}
      {last?.data?.delivery ? <Text style={textStyle}>{last.data.delivery.state === "accepted" ? "현재 대화에 전달했습니다. 검증 결과는 별도로 확인합니다." : `전달 상태: ${last.data.delivery.state}`}</Text> : null}
      {last?.data?.id && last?.data?.state_version && last?.data?.delivery ? button("이 실행 취소 요청 (전달 후에는 확인 필요)", async () => { await submit("execution.cancel", { execution_id: last.data.id, expected_state_version: last.data.state_version }); }) : null}
      {props.addComposerAttachment && goal ? button("현재 작업을 대화에 첨부", async () => { const pack = await query({ ...binding, sessionId: connection!.sessionId, query: "context", payload: { goal_id: goal, stage: "implementation" } });
        props.addComposerAttachment!({ sourceId: "intent-invocation", item: { id: `skip-${goal}`, identifier: goal, title: "SKIP 현재 작업", url: `https://local.skip.invalid/goals/${goal}`, resourceType: "skip-context", text: JSON.stringify(pack) } }); }) : null}
      </> : null}
      {button("새로고침", () => refresh())}
    </> : null}
    {button(details ? "상세 접기" : "상세 보기", async () => setDetails(!details))}
    {details ? <Text style={{ color, fontFamily: "monospace", fontSize: 12 }}>{JSON.stringify({ projectId: connection?.projectId, goal, last }, null, 2)}</Text> : null}
  </ContinuityScroll>}
      </View> : null}
    </View>
  </View>;
}
