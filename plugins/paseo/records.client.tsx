import { type PluginWorkspacePanelProps, useRpc, useWorkspace } from "@getpaseo/plugin";
import { useEffect, useMemo, useRef, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import { useQuery } from "@tanstack/react-query";
import { getDecisionInbox, getIntentRecordAttachment, listIntentRecords, readIntentRecord, readRecordGroup } from "./records.shared";
import { projectReading, statusLabel, type RecordMeta, type Excerpt } from "./records.presentation";
import { MarkdownDocument } from "./records.document";
import { recordCaller } from "./records.caller";

type Doc = { record: RecordMeta; text: string };
export function IntentRecordsPanel(props: PluginWorkspacePanelProps) {
  // A host workspace switch discards tabs, requests and previous project content.
  return <Reader key={props.workspaceId} {...props} />;
}
function Reader({ theme, layout, workspaceId, addComposerAttachment }: PluginWorkspacePanelProps) {
  const workspace = useWorkspace(workspaceId, ({ projectId, projectRootPath }) => ({ projectId, projectRootPath }));
  const list = useRpc(listIntentRecords), read = useRpc(readIntentRecord), groupRead = useRpc(readRecordGroup);
  const inbox = useRpc(getDecisionInbox), attachment = useRpc(getIntentRecordAttachment);
  const [scope, setScope] = useState<"now" | "history">("now"), [query, setQuery] = useState(""), [search, setSearch] = useState("");
  const [selected, select] = useState<string | null>(null), [tabs, setTabs] = useState<Doc[]>([]), [active, setActive] = useState<string | null>(null);
  const [expanded, setExpanded] = useState<Record<string, boolean>>({}), [notice, setNotice] = useState("");
  const [attaching, setAttaching] = useState(false), [width, setWidth] = useState(0);
  const [opening, setOpening] = useState(false);
  const openSequence = useRef(0), listOffset = useRef(0), listScroll = useRef<ScrollView>(null);
  const c = theme.colors, narrow = layout.compact || width < 820;
  const listing = useQuery({ queryKey: ["skip-records", workspace, scope, search], enabled: !!workspace,
    queryFn: () => list({ paseoProjectId: workspace!.projectId, projectRootPath: workspace!.projectRootPath, scope, query: search }) });
  const groups = useMemo(() => {
    const map = new Map<string, RecordMeta[]>();
    for (const record of listing.data?.items ?? []) { const key = record.goal ?? "__project__"; map.set(key, [...(map.get(key) ?? []), record]); }
    return [...map].map(([key, records]) => ({ key, records, title: key === "__project__" ? "프로젝트 전체" : records[0].title.replace(/\s*(영향 분석|시스템 설계|제품 요구사항|구현 작업 계획)\s*$/, "") || key }));
  }, [listing.data]);
  const chosen = groups.find(g => g.key === selected);
  const detail = useQuery({ queryKey: ["skip-reading", workspace, selected, scope, chosen?.records.map(r => r.relativePath)], enabled: !!chosen,
    queryFn: () => groupRead({ projectId: chosen!.records[0].projectId, paths: chosen!.records.slice(0, 24).map(r => r.relativePath) }) });
  const decisions = useQuery({ queryKey: ["skip-inbox", workspace, selected], enabled: !!workspace && !!chosen && selected !== "__project__" && scope === "now",
    retry: false, queryFn: () => inbox({ paseoProjectId: workspace!.projectId, projectRootPath: workspace!.projectRootPath, goal: selected! }) });
  const reading = useMemo(() => projectReading(detail.data?.documents ?? []), [detail.data]);
  const doc = tabs.find(d => d.record.relativePath === active);
  useEffect(() => { if (!selected && !active) listScroll.current?.scrollTo({ y: listOffset.current, animated: false }); }, [selected, active, narrow]);
  const button = (label: string, action: () => void, primary = false) => <Pressable accessibilityRole="button" onPress={action} style={{ paddingVertical: 9, paddingHorizontal: 12, borderRadius: 8, backgroundColor: primary ? c.accent : c.surface0, borderColor: c.foregroundMuted, borderWidth: primary ? 0 : 0.5 }}><Text style={{ color: primary ? c.accentForeground : c.foreground, fontSize: 14 }}>{label}</Text></Pressable>;
  const text = (value: string, muted = false) => <Text selectable style={{ color: muted ? c.foregroundMuted : c.foreground, fontSize: 16, lineHeight: 27 }}>{value}</Text>;
  const heading = (value: string) => <Text style={{ color: c.foreground, fontSize: 18, fontWeight: "700", marginTop: 8 }}>{value}</Text>;
  const fold = (key: string, title: string, body: React.ReactNode) => <View style={{ gap: 12 }}>{button(`${expanded[key] ? "▾" : "▸"} ${title}`, () => setExpanded(s => ({ ...s, [key]: !s[key] })))}{expanded[key] && body}</View>;
  const open = async (record: RecordMeta) => {
    const sequence = ++openSequence.current; setNotice(""); setOpening(true);
    try { const next = await read({ projectId: record.projectId, relativePath: record.relativePath });
      if (sequence !== openSequence.current) return;
      setTabs(old => [...old.filter(d => d.record.relativePath !== record.relativePath), next]); setActive(record.relativePath);
    } catch (e) { if (sequence === openSequence.current) setNotice(String(e)); }
    finally { if (sequence === openSequence.current) setOpening(false); }
  };
  const excerpts = (items: Excerpt[], empty: string) => items.length ? items.map((item, index) => <View key={`${item.path}:${item.line}:${index}`} style={{ gap: 4 }}>
    {text(item.text)}<Pressable accessibilityRole="button" onPress={() => { const record = detail.data?.documents.find(d => d.record.relativePath === item.path)?.record; if (record) void open(record); }}><Text style={{ color: c.accent, fontSize: 12 }}>원문 · {item.path.split("/").at(-1)}:{item.line}</Text></Pressable>
  </View>) : text(empty, true);
  const attach = async (record: RecordMeta) => {
    if (attaching) return; setAttaching(true); setNotice("");
    try {
      if (addComposerAttachment) { const item = await attachment({ projectId: record.projectId, relativePath: record.relativePath }); await addComposerAttachment({ sourceId: "intent-record", item }); setNotice("문서를 첨부했습니다."); }
      else { const caller = recordCaller(record); const clipboard = (globalThis as any).navigator?.clipboard; if (clipboard) { await clipboard.writeText(caller); setNotice("호출자를 복사했습니다."); } else setNotice(caller); }
    } catch (e) { setNotice(`첨부 실패: ${String(e)}`); } finally { setAttaching(false); }
  };
  const choose = (key: string | null) => { openSequence.current++; setOpening(false); select(key); setActive(null); setNotice(""); };
  if (!workspace) return text("프로젝트 정보를 사용할 수 없습니다.");
  return <View onLayout={e => setWidth(e.nativeEvent.layout.width)} style={{ flex: 1, minHeight: 0, padding: narrow ? 14 : 24, gap: 16, backgroundColor: c.surface0 }}>
    <View style={{ flexDirection: "row", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
      <Text style={{ color: c.foreground, fontSize: 24, fontWeight: "700", flex: 1 }}>SKIP 기록</Text>
      {button("현재 상태", () => { setScope("now"); choose(null); }, scope === "now")}
      {button("결정 이력", () => { setScope("history"); choose(null); }, scope === "history")}
      {button("새로고침", () => { void listing.refetch(); if (chosen) void detail.refetch(); if (chosen && selected !== "__project__" && scope === "now") void decisions.refetch(); })}
    </View>
    <View style={{ flexDirection: "row", gap: 8 }}><TextInput accessibilityLabel="기록 검색" placeholder="작업 제목 또는 문서 검색" placeholderTextColor={c.foregroundMuted} value={query} onChangeText={setQuery} onSubmitEditing={() => { setSearch(query); choose(null); }} style={{ flex: 1, minWidth: 0, color: c.foreground, borderColor: c.foregroundMuted, borderWidth: 0.5, borderRadius: 8, padding: 10 }} />{button("검색", () => { setSearch(query); choose(null); })}</View>
    {tabs.length > 0 && <ScrollView horizontal style={{ flexGrow: 0, flexShrink: 0 }} contentContainerStyle={{ gap: 8 }}>
      {button("작업 요약", () => setActive(null), !active)}{tabs.map(d => <View key={d.record.relativePath} style={{ flexDirection: "row", alignItems: "center", maxWidth: 280 }}>{button(d.record.title.length > 20 ? d.record.title.slice(0, 20) + "…" : d.record.title, () => setActive(d.record.relativePath), active === d.record.relativePath)}<Pressable accessibilityRole="button" accessibilityLabel={`${d.record.title} 닫기`} onPress={() => { setTabs(s => s.filter(x => x !== d)); if (active === d.record.relativePath) setActive(null); }} style={{ padding: 10 }}><Text style={{ color: c.foregroundMuted }}>×</Text></Pressable></View>)}
    </ScrollView>}
    {notice ? <Text selectable accessibilityRole="alert" style={{ color: c.foreground, fontSize: 14 }}>{notice}</Text> : null}
    {(listing.isFetching || opening) && <ActivityIndicator color={c.accent} />}
    {listing.error && text(`목록을 읽지 못했습니다: ${String(listing.error)}`)}
    <View style={{ flex: 1, minHeight: 0, flexDirection: narrow ? "column" : "row", gap: 28 }}>
      {(!narrow || (!chosen && !doc)) && <ScrollView ref={listScroll} onScroll={e => { listOffset.current = e.nativeEvent.contentOffset.y; }} scrollEventThrottle={100} style={{ width: narrow ? "100%" : 260, flex: narrow ? 1 : undefined }} contentContainerStyle={{ gap: 8, paddingBottom: 24 }}>
        {!groups.length && !listing.isLoading && text("조건에 맞는 기록이 없습니다.", true)}
        {groups.map(g => <Pressable key={g.key} accessibilityRole="button" accessibilityState={{ selected: selected === g.key }} onPress={() => choose(g.key)} style={{ padding: 14, gap: 8, borderRadius: 10, borderLeftWidth: 3, borderColor: selected === g.key ? c.accent : "transparent", backgroundColor: c.surface0 }}>
          <Text style={{ color: c.foreground, fontSize: 16, fontWeight: "600", lineHeight: 23 }}>{g.title}</Text>
          <Text style={{ color: c.foregroundMuted, fontSize: 13 }}>{statusLabel(g.records[0])}</Text>
          <Text style={{ color: c.foregroundMuted, fontSize: 12 }}>{g.records[0].verifiedAt ? `확인 ${g.records[0].verifiedAt}` : "확인 시점 미기록"}</Text>
        </Pressable>)}
      </ScrollView>}
      {(chosen || doc) ? <View style={{ flex: 1, minWidth: 0, gap: 12 }}>
        {narrow && button("‹ 작업 목록", () => choose(null))}
        {doc ? <>
          {heading(doc.record.title)}
          <View style={{ flexDirection: "row", gap: 8 }}>{button(attaching ? "첨부 중…" : addComposerAttachment ? "문서 첨부" : "호출자 복사", () => void attach(doc.record), true)}</View>
          {fold("metadata", "문서 정보", text(`${doc.record.relativePath}\n확인: ${doc.record.verifiedAt ?? "미기록"}\nrevision: ${doc.record.sourceRevision ?? "미기록"}`, true))}
          <MarkdownDocument key={doc.record.relativePath} markdown={doc.text} theme={theme} compact={narrow} />
        </> : <ScrollView contentContainerStyle={{ gap: 20, paddingBottom: 40, maxWidth: 720, width: "100%", alignSelf: "center" }}>
          <View style={{ gap: 8 }}><Text style={{ color: c.foreground, fontSize: 26, fontWeight: "700", lineHeight: 34 }}>{chosen!.title}</Text>{text(statusLabel(chosen!.records[0]), true)}{text("기록 기준 요약 · 현재 코드와의 일치 여부는 별도 확인", true)}</View>
          {detail.isFetching && <ActivityIndicator color={c.accent} />}
          {detail.error && text(`상세 확인 실패: ${String(detail.error)}`)}
          {detail.data && <>
            {detail.data.errors.map(e => <View key={e.path}>{text(`읽지 못한 기록: ${e.path}\n${e.message}`)}</View>)}
            {chosen!.records.length > 24 && text("문서가 많아 첫 24개만 요약했습니다. 나머지는 원문에서 확인하세요.")}
            {reading.warnings.map(w => <View key={w}>{text(`! ${w}`)}</View>)}
            {scope === "now" ? <>
              {heading("내 결정")}
              {selected === "__project__" ? text("작업을 선택하면 해당 결정 요청을 확인할 수 있습니다.", true) : decisions.isLoading ? text("결정 기록 확인 중…", true) : decisions.error ? text("결정 기록 확인 안 됨 — 조회에 실패했습니다.") : decisions.data ? decisions.data.items.length ? decisions.data.items.map(item => <View key={item.id} style={{ gap: 8, borderLeftWidth: 3, borderColor: c.accent, paddingLeft: 14 }}>{text(item.summary || `${item.action ?? item.kind} 확인 필요`)}{text(item.status, true)}{item.reasons.map((reason, i) => <View key={i}>{text(reason, true)}</View>)}</View>) : text("현재 Inbox에 확인할 항목이 없습니다.", true) : text("결정 기록 확인 안 됨", true)}
              {heading("현재 상태")}{excerpts(reading.summary, "요약할 현재 사실을 찾지 못했습니다. 원문을 확인하세요.")}
              {heading("확인된 것 · 기록 기준")}{excerpts(reading.checks, "명시된 검증 결과를 찾지 못했습니다.")}
              {heading("아직 확인하지 못한 것")}{excerpts(reading.gaps, "미검증 항목이 명시되어 있지 않습니다. 전체 검증 완료를 뜻하지 않습니다.")}
              {fold("decisions", "적용된 제품 결정", excerpts(reading.decisions, "결정 기록 확인 안 됨"))}
            </> : <>{heading("결정과 이유")}{excerpts(reading.decisions, "구조화된 결정을 찾지 못했습니다. 아래 원문에서 확인하세요.")}{text("과거 문서의 결정 기록입니다. 현재 승인 효력을 뜻하지 않습니다.", true)}</>}
          </>}
          {fold("originals", `원문 문서 · ${chosen!.records.length}`, <View style={{ gap: 12 }}>{chosen!.records.map(record => <View key={record.relativePath}>{button(record.title, () => void open(record))}</View>)}</View>)}
        </ScrollView>}
      </View> : !narrow && <View style={{ flex: 1, padding: 24 }}>{heading("어떤 작업을 확인할까요?")}{text("왼쪽에서 작업을 선택하면 상태와 필요한 결정, 검증 근거를 함께 볼 수 있습니다.", true)}</View>}
    </View>
  </View>;
}
