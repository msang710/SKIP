import React, { useEffect, useState, useRef } from "react";
import { Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useRpc, type PluginAgentPanelProps, type PluginWorkspacePanelProps } from "@getpaseo/plugin";
import { MarkdownDocument } from "./records.document";
import { closeCore, connectCore, queryCore, userCore } from "./core.shared";

type Props = PluginAgentPanelProps | PluginWorkspacePanelProps;
type Connection = { sessionId: string; projectId: string; target: string; canStart: boolean };
const newId = () => `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;

export function CorePanel(props: Props) {
  const { theme, layout, workspaceId } = props;
  const agentId = props.context === "agent" ? props.agentId : undefined;
  const connect = useRpc(connectCore), query = useRpc(queryCore), user = useRpc(userCore), close = useRpc(closeCore);
  const [uiInstanceId] = useState(newId), [connection, setConnection] = useState<Connection | null>(null);
  const [status, setStatus] = useState<any>(null), [inbox, setInbox] = useState<any[]>([]), [risks, setRisks] = useState<any[]>([]);
  const [goal, setGoal] = useState<string | undefined>(), [input, setInput] = useState("");
  const [choice, setChoice] = useState<Record<string, string>>({}), [error, setError] = useState("");
  const [historyRows, setHistoryRows] = useState<any[]>([]), [historyCursor, setHistoryCursor] = useState<string | null>(null), [historySearch, setHistorySearch] = useState("");
  const [panelWidth, setPanelWidth] = useState(0), [mobileDetail, setMobileDetail] = useState(false);
  const [goals, setGoals] = useState<any[]>([]), [goalCursor, setGoalCursor] = useState<string | null>(null);
  const [recordKind, setRecordKind] = useState<string | undefined>();
  const [historical, setHistorical] = useState<any>(null);
  const [busy, setBusy] = useState(false), [details, setDetails] = useState(false), [last, setLast] = useState<any>(null);
  const binding = { uiInstanceId, workspaceId, agentId };
  const pendingKeys = useRef(new Map<string, string>());
  const generation = useRef(0);
  const wide = panelWidth >= 760;
  const color = theme.colors.foreground, muted = theme.colors.foregroundMuted;
  const textStyle = { color, fontSize: 16, lineHeight: 25 };
  const button = (label: string, action: () => Promise<void>, disabled = false) => <Pressable accessibilityRole="button" accessibilityState={{ disabled: disabled || busy }}
    disabled={disabled || busy} onPress={() => void run(action)} style={{ padding: 12, borderWidth: 1, borderColor: theme.colors.foregroundMuted, borderRadius: 8, opacity: disabled || busy ? 0.5 : 1 }}>
    <Text style={{ color }}>{label}</Text></Pressable>;
  async function run(action: () => Promise<void>) { setBusy(true); setError(""); try { await action(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); } finally { setBusy(false); } }
  async function refresh(c = connection, g: string | null | undefined = goal) {
    if (!c) return;
    const expectedGeneration = generation.current;
    const bound = { ...binding, sessionId: c.sessionId };
    const [s, i, h] = await Promise.all([query({ ...bound, query: "status", payload: g ? { goal_id: g } : { limit: 100 } }), query({ ...bound, query: "inbox", payload: g ? { goal_id: g } : {} }), query({ ...bound, query: "record.list", payload: { ...(g ? { goal_id: g } : {}), limit: 30 } })]);
    if (expectedGeneration !== generation.current) return;
    setHistoryRows((h as any).data.items); setHistoryCursor((h as any).data.next_cursor); setHistorical(null); setHistorySearch(""); setRecordKind(undefined);
    if (!g) { setGoals((s as any).data.goals); setGoalCursor((s as any).data.next_cursor); }
    setStatus((s as any).data); setInbox((i as any).data.items); setChoice({});
    if (g) { const r = await query({ ...bound, query: "risks", payload: { goal_id: g } }); if (expectedGeneration === generation.current) setRisks((r as any).data.assessments); }
    else setRisks([]);
  }
  useEffect(() => {
    generation.current += 1; pendingKeys.current.clear();
    let gone = false, current: Connection | null = null;
    setConnection(null); setStatus(null); setGoals([]); setHistoryRows([]); setHistoryCursor(null); setGoalCursor(null); setMobileDetail(false); setInbox([]); setGoal(undefined); setLast(null); setHistorical(null);
    void connect(binding).then(async c => {
      current = c;
      if (gone) { await close({ ...binding, sessionId: c.sessionId }); return; }
      setConnection(c);
      try { await refresh(c, null); } catch (e) { if (!gone) setError(e instanceof Error ? e.message : String(e)); }
    }).catch(e => { if (!gone) setError(String(e)); });
    return () => { generation.current += 1; gone = true; if (current) void close({ ...binding, sessionId: current.sessionId }).catch(() => {}); };
  }, [workspaceId, agentId, props.host.id]);
  async function submit(command: "project.activate" | "request.submit" | "decision.select" | "execution.prepare" | "execution.cancel" | "settings.update", payload: Record<string, unknown>) {
    if (!connection) return;
    const signature = JSON.stringify({ command, payload });
    const key = pendingKeys.current.get(signature) ?? newId(); pendingKeys.current.set(signature, key);
    const value = await user({ ...binding, sessionId: connection.sessionId, command, payload, key });
    setLast(value); await refresh(); pendingKeys.current.delete(signature); return value as any;
  }
  async function readHistory(append = false, filter: string | null | undefined = recordKind) {
    const expected = generation.current;
    const response = await query({ ...binding, sessionId: connection!.sessionId, query: filter === "source" ? "history" : "record.list", payload: {
      ...(filter && filter !== "source" ? { kind: filter } : {}), ...(goal ? { goal_id: goal } : {}), ...(historySearch ? { search: historySearch } : {}), ...(append && historyCursor ? { cursor: historyCursor } : {}), limit: 30,
    } });
    if (expected !== generation.current) return;
    const data = (response as any).data;
    setHistoryRows(previous => append ? [...previous, ...data.items] : data.items); setHistoryCursor(data.next_cursor); setHistorical(null);
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
  async function selectGoal(id?: string) {
    generation.current += 1;
    setGoal(id); setHistorical(null); setHistoryRows([]); setMobileDetail(false);
    await refresh(connection, id ?? null);
  }
  async function openDocument(document: any) {
    const expected = generation.current;
    const r = await query({ ...binding, sessionId: connection!.sessionId, query: document.revision ? "record" : "history.record", payload: document.revision ? { kind: document.kind, id: document.id, revision: document.revision } : { id: document.id } });
    if (expected !== generation.current) return;
    const data = (r as any).data;
    if (data.fields) {
      const names: Record<string,string> = { intent:"목표", success_definition:"완료 기준", question:"결정", rationale:"근거", risk_summary:"위험·영향", statement:"요구사항", design_body:"설계", scope_description:"범위", alternatives_body:"대안", rollback_body:"복구", instruction_body:"작업", completion_definition:"완료 기준", summary:"근거·결과", method:"기록 방법", observed_at:"관찰 시점" };
      const body = Object.entries(names).filter(([key]) => data.fields[key] && !(key !== "design_body" && data.fields.design_body?.includes(data.fields[key]))).map(([key,label]) => `## ${label}\n\n${data.fields[key]}`).join("\n\n");
      const childNames: Record<string,string> = {options:"선택지",criteria:"인수 기준",checks:"검증 항목"};
      const children = Object.entries(childNames).flatMap(([key,label]) => (data.children[key] ?? []).map((row:any) => `## ${label} · ${row.title ?? row.label ?? row.criterion_id ?? row.check_id ?? ""}\n\n${row.description ?? row.design_body ?? ""}`)).join("\n\n");
      setHistorical({ ...data, title: data.fields.title ?? data.fields.question ?? document.title, source_path: data.origin?.source_path ?? data.origin?.source_key ?? "", historical_status: data.origin?.source_status ?? data.lifecycle, body: body+"\n\n"+children, next_offset: null });
    } else setHistorical(data);
    setMobileDetail(true);
  }
  const navItem = (title: string, selected: boolean, action: () => Promise<void>, subtitle?: string) =>
    <Pressable accessibilityRole="button" accessibilityState={{ selected, disabled: busy }} disabled={busy} onPress={() => void run(action)}
      style={{ padding: 12, gap: 4, borderLeftWidth: 3, borderLeftColor: selected ? theme.colors.accent : "transparent", backgroundColor: selected ? theme.colors.surface0 : "transparent", opacity: busy ? 0.6 : 1 }}>
      <Text style={{ color: selected ? theme.colors.accent : color, fontWeight: selected ? "700" : "400", lineHeight: 22 }}>{title}</Text>
      {subtitle ? <Text numberOfLines={2} style={{ color: muted, fontSize: 12 }}>{subtitle}</Text> : null}
    </Pressable>;
  return <View onLayout={event => setPanelWidth(event.nativeEvent.layout.width)} style={{ flex: 1, minHeight: 0, backgroundColor: theme.colors.surface0 }}>
    <View style={{ padding: 16, gap: 6, borderBottomWidth: 1, borderColor: muted }}>
      <Text style={{ color, fontSize: 22, fontWeight: "700" }}>SKIP</Text>
      <Text numberOfLines={1} style={{ color: muted }}>{connection?.target ?? "현재 연결 확인 중"}</Text>
      {error ? <Text accessibilityRole="alert" style={textStyle}>{error}</Text> : null}
      {!wide ? button(mobileDetail ? "← 목표·문서 목록" : "선택한 목표 상세 →", async () => setMobileDetail(!mobileDetail)) : null}
    </View>
    <View style={{ flex: 1, minHeight: 0, flexDirection: "row" }}>
      {wide || !mobileDetail ? <View accessibilityLabel="목표와 문서 목록" style={{ width: wide ? 300 : "100%", flexGrow: 0, flexShrink: 0, minHeight: 0, borderRightWidth: wide ? 1 : 0, borderColor: muted }}>
        <ScrollView style={{ flexGrow: 0, maxHeight: "42%", flexShrink: 1 }} contentContainerStyle={{ padding: 12, gap: 8 }}>
        <Text style={{ color, fontSize: 18, fontWeight: "700", padding: 8 }}>목표</Text>
        {navItem("프로젝트 전체", !goal, () => selectGoal())}
        {goals.map(g => <View key={g.id}>{navItem(g.fields.title, goal === g.id, () => selectGoal(g.id))}</View>)}
        {goalCursor ? button("목표 더 보기", async () => {
          const r = await query({ ...binding, sessionId: connection!.sessionId, query: "status", payload: { cursor: goalCursor, limit: 100 } });
          setGoals(previous => [...previous, ...(r as any).data.goals]); setGoalCursor((r as any).data.next_cursor);
        }) : null}
        </ScrollView>
        <ScrollView style={{ flex: 1, borderTopWidth: 1, borderColor: muted }} contentContainerStyle={{ padding: 12, gap: 8 }}>
        <Text style={{ color, fontSize: 18, fontWeight: "700", padding: 8 }}>문서 · {selectedGoal?.fields.title ?? "전체"}</Text>
        {navItem("목표 현황", !historical, async () => { setHistorical(null); setMobileDetail(true); })}
        <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 6 }}>
          {([[undefined,"전체"],["decision","결정"],["requirement","요구"],["plan","설계"],["work_item","작업"],["evidence","근거·검증"],["source","참고 원문"]] as const).map(([kind,label]) =>
            <Pressable key={label} disabled={busy} accessibilityRole="button" accessibilityState={{selected:recordKind===kind}} onPress={() => void run(async () => {setRecordKind(kind); await readHistory(false,kind ?? null);})} style={{padding:8,borderBottomWidth:recordKind===kind?2:0,borderColor:theme.colors.accent}}><Text style={{color:recordKind===kind?theme.colors.accent:muted}}>{label}</Text></Pressable>)}
        </View>
        <TextInput accessibilityLabel="기존 기록 검색" placeholder="기록 제목 검색" placeholderTextColor={muted} value={historySearch}
          onChangeText={value => { setHistorySearch(value); setHistoryCursor(null); }} onSubmitEditing={() => void run(() => readHistory())}
          style={{ ...textStyle, borderWidth: 1, borderColor: muted, borderRadius: 8, padding: 10 }} />
        {button("기록 검색", () => readHistory(), !connection)}
        {historyRows.map(document => <View key={document.id}>{navItem(document.title, historical?.id === document.id, () => openDocument(document), document.origin ? `${document.origin.source_key} · ${document.origin.source_status}` : document.source_path ?? document.kind)}</View>)}
        {!historyRows.length ? <Text style={{ color: muted, padding: 8 }}>표시할 문서가 없습니다.</Text> : null}
        {historyCursor ? button("기록 더 보기", () => readHistory(true)) : null}
        </ScrollView>
      </View> : null}
      {wide || mobileDetail ? <View accessibilityLabel="선택한 목표와 문서 상세" style={{ flex: 1, minWidth: 0, minHeight: 0 }}>
        {historical ? <View style={{ flex: 1, minHeight: 0, padding: wide ? 24 : 16, gap: 12 }}>
          <Text style={{ color: muted }}>{selectedGoal?.fields.title ?? "프로젝트 기록"}</Text>
          <Text style={{ color, fontSize: 24, fontWeight: "700" }}>{historical.title}</Text>
          <Text style={{ color: muted }}>{historical.source_path} · 기록 상태: {historical.historical_status}</Text>
          <Text style={{ color: muted }}>{historical.origin ? "기존 결정과 작업 상태를 복원한 기록입니다. 현재 실행 권한은 별도로 확인합니다." : "공통 Core 기록"}</Text>
          {historical.origin?.unresolved_json && historical.origin.unresolved_json !== "[]" ? <Text style={{color:muted}}>연결 확인 필요: {JSON.parse(historical.origin.unresolved_json).join(" · ")}</Text> : null}
          <View style={{flexDirection:"row",flexWrap:"wrap",gap:6}}>
            {Object.entries({decisions:"decision",requirements:"requirement",plan_items:"plan",dependencies:"work_item"}).flatMap(([key,kind]) => (historical.children?.[key] ?? []).map((link:any,index:number) => {
              const id=link.decision_id ?? link.requirement_id ?? link.plan_id ?? link.depends_on_id;
              const revision=link.decision_revision ?? link.requirement_revision ?? link.plan_revision ?? link.depends_on_revision;
              return <View key={`${key}-${index}`}>{button(link.rationale ?? link.reason ?? "연결된 기록", () => openDocument({id,revision,kind,title:"연결된 기록"}))}</View>;
            }))}
          </View>
          <MarkdownDocument key={historical.id} markdown={historical.body ?? "원본 첨부 데이터가 DB에 보존되어 있습니다."} theme={theme} compact={!wide} />
          {historical.next_offset !== null ? button("본문 더 읽기", async () => {
            const r = await query({ ...binding, sessionId: connection!.sessionId, query: "history.record", payload: { id: historical.id, offset: historical.next_offset } });
            setHistorical({ ...(r as any).data, body: (historical.body ?? "") + ((r as any).data.body ?? "") });
          }) : null}
        </View> : <ScrollView style={{ flex: 1 }} contentContainerStyle={{ padding: wide ? 28 : 16, gap: 18, maxWidth: 900, width: "100%", alignSelf: "center" }}>
          <Text style={{ color, fontSize: 24, fontWeight: "700" }}>{selectedGoal?.fields.title ?? "프로젝트 현황"}</Text>
          {connection && !status ? button("이 프로젝트에서 사용", async () => { await submit("project.activate", { name: "현재 프로젝트" }); }) : null}
          {status ? <>
      {selectedGoal ? <View style={{gap:8}}><Text style={{color,fontSize:18,fontWeight:"600"}}>목표</Text><Text selectable style={textStyle}>{selectedGoal.fields.intent}</Text><Text style={{color:muted}}>완료 기준</Text><Text selectable style={textStyle}>{selectedGoal.fields.success_definition}</Text></View> : null}
      <Text style={{ color, fontSize: 20, fontWeight: "600" }}>결과</Text>
      {!status.facts.length ? <Text style={{ color: muted }}>아직 확인된 현재 기록이 없습니다. 요청부터 시작하세요.</Text> : status.facts.map((f: any) => <View key={f.id} style={{ gap: 4 }}>
        <Text style={textStyle}>{f.statement}</Text><Text style={{ color: muted }}>{f.origin ? "기존 관찰 기록" : f.freshness === "current" ? "현재 소스 확인" : "재확인 필요"} · {f.provenance === "agent_report" ? "에이전트 보고" : f.provenance}</Text>
      </View>)}
      <TextInput accessibilityLabel="개발 요청" value={input} onChangeText={setInput} multiline placeholder="무엇을 바꾸고 싶나요?" placeholderTextColor={muted}
        style={{ ...textStyle, minHeight: 70, padding: 12, borderWidth: 1, borderColor: theme.colors.foregroundMuted, borderRadius: 8 }} />
      {button("요청 저장", async () => { const r = await submit("request.submit", { text: input, operation: "implement", ...(goal ? { goal_id: goal } : {}) });
        if (r?.data.goal) { setGoal(r.data.goal.id); await refresh(connection, r.data.goal.id); } setInput(""); }, !input.trim())}
      {inbox.map(card => <View key={`${card.id}:${card.revision}`} style={{ padding: 16, gap: 12, borderWidth: 1, borderColor: theme.colors.foregroundMuted, borderRadius: 12 }}>
        <Text style={{ color: muted }}>결정 필요</Text><Text style={{ ...textStyle, fontWeight: "600", fontSize: 19 }}>{card.fields.question}</Text>
        {card.children.options.map((option: any) => <Pressable key={option.option_id} accessibilityRole="radio" accessibilityState={{ checked: choice[card.id] === option.option_id }}
          onPress={() => setChoice(v => ({ ...v, [card.id]: option.option_id }))} style={{ padding: 12, gap: 4, borderWidth: 1, borderColor: theme.colors.foregroundMuted, borderRadius: 8 }}>
          <Text style={textStyle}>{choice[card.id] === option.option_id ? "●" : "○"} {option.label}{option.recommended ? " · 추천" : ""}</Text>
          <Text style={{ color: muted }}>{option.consequences}</Text>
        </Pressable>)}
        <Text style={textStyle}>{card.fields.rationale}</Text><Text style={{ color: muted }}>위험: {card.fields.risk_summary}</Text>
        {card.selection ? <Text style={{ color: muted }}>저장된 선택: {card.children.options.find((o: any) => o.option_id === card.selection.option_id)?.label}</Text> : null}
        {card.selection_stale ? <Text style={textStyle}>질문이 변경됐습니다. 다시 확인하세요.</Text> : null}
        {button("선택 저장", async () => { await submit("decision.select", { decision_id: card.id, revision: card.revision, option_id: choice[card.id] }); }, !choice[card.id])}
        {nextWork && connection?.canStart ? button(`선택 확정하고 ${nextWork.fields.operation === "implement" ? "구현" : nextWork.fields.operation === "design" ? "설계" : "작업 진행"}`,
          () => execute(nextWork, { decision_id: card.id, revision: card.revision, option_id: choice[card.id] }), !choice[card.id]) : null}
      </View>)}
      {workItems.map((w: any) => <View key={w.id} style={{ gap: 8 }}><Text style={textStyle}>{w.fields.title}</Text>
        {button(w.fields.operation === "implement" ? "이 작업 구현" : "이 작업 진행", () => execute(w), !connection?.canStart)}
      </View>)}
      <Text style={{ color, fontSize: 20, fontWeight: "600" }}>확인</Text>
      {status.checks.map((c: any) => <Text key={c.id} style={textStyle}>{c.origin ? "기록" : c.result === "PASS" ? "✓" : "!"} {c.summary} · {c.surface} · {c.origin ? c.origin.source_status : c.freshness === "stale" ? "재확인 필요" : c.result}</Text>)}
      <Text style={{ color, fontSize: 20, fontWeight: "600" }}>남은 일</Text>
      {status.remaining.map((r: any) => <Text key={`${r.work_id}:${r.check_id}`} style={textStyle}>! {r.description} · {r.state}</Text>)}
      {!connection?.canStart ? <Text style={{ color: muted }}>현재 대화의 SKIP 패널에서 연결을 확인하면 작업을 전달할 수 있습니다.</Text> : null}
      {last?.data?.delivery ? <Text style={textStyle}>{last.data.delivery.state === "accepted" ? "현재 대화에 전달했습니다. 검증 결과는 별도로 확인합니다." : `전달 상태: ${last.data.delivery.state}`}</Text> : null}
      {last?.data?.id && last?.data?.state_version && last?.data?.delivery ? button("이 실행 취소 요청 (전달 후에는 확인 필요)", async () => { await submit("execution.cancel", { execution_id: last.data.id, expected_state_version: last.data.state_version }); }) : null}
      {props.addComposerAttachment && goal ? button("현재 작업을 대화에 첨부", async () => { const pack = await query({ ...binding, sessionId: connection!.sessionId, query: "context", payload: { goal_id: goal, stage: "implementation" } });
        props.addComposerAttachment!({ sourceId: "intent-invocation", item: { id: `skip-${goal}`, identifier: goal, title: "SKIP 현재 작업", url: `https://local.skip.invalid/goals/${goal}`, resourceType: "skip-context", text: JSON.stringify(pack) } }); }) : null}
      {button("새로고침", () => refresh())}
    </> : null}
    {button(details ? "상세 접기" : "상세 보기", async () => setDetails(!details))}
    {details ? <Text style={{ color, fontFamily: "monospace", fontSize: 12 }}>{JSON.stringify({ projectId: connection?.projectId, goal, last }, null, 2)}</Text> : null}
  </ScrollView>}
      </View> : null}
    </View>
  </View>;
}
