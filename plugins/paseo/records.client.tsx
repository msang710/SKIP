import { type PluginTheme, type PluginWorkspacePanelProps, useRpc, useWorkspace } from "@getpaseo/plugin";
import { Fragment, useEffect, useMemo, useState } from "react";
import { ActivityIndicator, Pressable, ScrollView, Text, TextInput, View } from "react-native";
import type { output as ZodOutput } from "zod";
import { recordCaller } from "./records.caller";
import { getDecisionInbox, getIntentRecordAttachment, listIntentRecords, readIntentRecord, recordSummarySchema } from "./records.shared";

type RecordSummary = ZodOutput<typeof recordSummarySchema>;

const ARTIFACT_PURPOSE: Record<string, string> = {
  impact: "영향 분석",
  prd: "제품 목표",
  user_stories: "사용자 스토리",
  system_design: "시스템 설계",
  tasks: "구현 계획",
  index: "현재 상태 안내",
  system: "현재 시스템",
  validation: "검증 상태",
};

const ARTIFACT_ORDER = ["impact", "prd", "user_stories", "system_design", "tasks", "index", "system", "validation"];

function featureTitle(records: RecordSummary[], scope: "now" | "history"): string {
  if (scope === "now") {
    const goalRecord = records.find(({ goal }) => goal);
    return goalRecord?.title ?? "현재 구현 상태";
  }
  const preferred = [...records].sort((a, b) => ARTIFACT_ORDER.indexOf(a.artifact) - ARTIFACT_ORDER.indexOf(b.artifact))[0];
  return (preferred?.title ?? preferred?.goal ?? "제목 없는 설계")
    .replace(/^QuickHack\s*/i, "")
    .replace(/\s*(코드 리뷰\s*)?(영향 분석|영향 조사|요구사항|제품 요구사항|사용자 스토리|시스템 설계|구현 작업 계획|구현 작업|작업 계획|작업)\s*$/u, "")
    .trim();
}

function groupRecords(items: RecordSummary[], scope: "now" | "history") {
  const groups = new Map<string, RecordSummary[]>();
  for (const item of items) {
    const key = scope === "now" ? (item.goal ?? "__current__") : (item.goal ?? "__ungrouped__");
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  return [...groups.entries()].map(([key, records]) => {
    const dateOf = (record: RecordSummary) => record.updated ?? record.created ?? "";
    const sortedRecords = records.sort((a, b) => {
      if (scope === "history") {
        const byDate = dateOf(b).localeCompare(dateOf(a));
        if (byDate) return byDate;
      }
      const aRank = ARTIFACT_ORDER.indexOf(a.artifact);
      const bRank = ARTIFACT_ORDER.indexOf(b.artifact);
      return (aRank < 0 ? 99 : aRank) - (bRank < 0 ? 99 : bRank) || a.title.localeCompare(b.title);
    });
    return {
      key,
      title: featureTitle(records, scope),
      slug: key.startsWith("__") ? undefined : key,
      latestDate: sortedRecords.reduce((latest, record) => dateOf(record) > latest ? dateOf(record) : latest, ""),
      records: sortedRecords,
    };
  }).sort((a, b) => scope === "history"
    ? b.latestDate.localeCompare(a.latestDate) || a.title.localeCompare(b.title)
    : a.title.localeCompare(b.title));
}

function InlineMarkdown({ text, theme }: { text: string; theme: PluginTheme }) {
  const tokens = text.split(/(`[^`]+`|\*\*[^*]+\*\*|\[[^\]]+\]\([^)]+\))/g);
  return <Text>{tokens.map((token, index) => {
    if (token.startsWith("`") && token.endsWith("`")) return <Text key={index} style={{ fontFamily: "monospace", backgroundColor: theme.colors.surface0 }}>{token.slice(1, -1)}</Text>;
    if (token.startsWith("**") && token.endsWith("**")) return <Text key={index} style={{ fontWeight: "700" }}>{token.slice(2, -2)}</Text>;
    const link = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
    if (link) return <Text key={index} style={{ color: theme.colors.accent, textDecorationLine: "underline" }}>{link[1]}</Text>;
    return <Fragment key={index}>{token}</Fragment>;
  })}</Text>;
}

function tableCells(line: string): string[] {
  return line.trim().replace(/^\|/, "").replace(/\|$/, "").split(/(?<!\\)\|/).map((cell) => cell.trim().replaceAll("\\|", "|"));
}

function markdownTable(text: string): { header?: string[]; rows: string[][]; columnCount: number } {
  const parsed = text.split("\n").map(tableCells);
  const hasHeader = parsed.length > 1 && parsed[1].every((cell) => /^:?-{3,}:?$/.test(cell));
  const header = hasHeader ? parsed[0] : undefined;
  const rows = hasHeader ? parsed.slice(2) : parsed;
  const columnCount = Math.max(header?.length ?? 0, ...rows.map((row) => row.length));
  return { header, rows, columnCount };
}

function MarkdownDocument({ markdown, theme, compact }: { markdown: string; theme: PluginTheme; compact: boolean }) {
  const lines = markdown.replaceAll("\r\n", "\n").replace(/^---\n[\s\S]*?\n---\n/, "").split("\n");
  const blocks: { type: string; text: string; language?: string }[] = [];
  let paragraph: string[] = [];
  let code: string[] | null = null;
  let language = "";
  const flush = () => { if (paragraph.length) { blocks.push({ type: "paragraph", text: paragraph.join(" ") }); paragraph = []; } };
  for (const line of lines) {
    if (line.startsWith("```")) {
      flush();
      if (code) { blocks.push({ type: "code", text: code.join("\n"), language }); code = null; language = ""; }
      else { code = []; language = line.slice(3).trim(); }
      continue;
    }
    if (code) { code.push(line); continue; }
    const heading = line.match(/^(#{1,4})\s+(.+)$/);
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    const ordered = line.match(/^\s*(\d+)\.\s+(.+)$/);
    const quote = line.match(/^>\s?(.*)$/);
    if (heading) { flush(); blocks.push({ type: `h${heading[1].length}`, text: heading[2] }); }
    else if (bullet) { flush(); blocks.push({ type: "bullet", text: bullet[1] }); }
    else if (ordered) { flush(); blocks.push({ type: "ordered", text: `${ordered[1]}. ${ordered[2]}` }); }
    else if (quote) { flush(); blocks.push({ type: "quote", text: quote[1] }); }
    else if (/^\s*([-*_])\1{2,}\s*$/.test(line)) { flush(); blocks.push({ type: "rule", text: "" }); }
    else if (/^\|.*\|$/.test(line)) {
      flush();
      const previous = blocks.at(-1);
      if (previous?.type === "table") previous.text += `\n${line}`;
      else blocks.push({ type: "table", text: line });
    }
    else if (!line.trim()) flush();
    else paragraph.push(line.trim());
  }
  flush();
  if (code) blocks.push({ type: "code", text: code.join("\n"), language });

  const sizes: Record<string, number> = { h1: compact ? 25 : 30, h2: compact ? 21 : 24, h3: 18, h4: 16 };
  return <View style={{ gap: compact ? 9 : 12, paddingBottom: 36 }}>
    {blocks.map((block, index) => {
      if (block.type === "rule") return <View key={index} style={{ height: 1, backgroundColor: theme.colors.foregroundMuted, opacity: 0.35, marginVertical: 4 }}/>;
      if (block.type === "code") return <View key={index} style={{ backgroundColor: theme.colors.surface0, borderColor: theme.colors.foregroundMuted, borderWidth: 1, borderRadius: 8, padding: 12 }}><Text style={{ color: theme.colors.foregroundMuted, fontSize: 11 }}>{block.language}</Text><Text selectable style={{ color: theme.colors.foreground, fontFamily: "monospace", lineHeight: 20 }}>{block.text}</Text></View>;
      if (block.type === "quote") return <View key={index} style={{ borderLeftColor: theme.colors.accent, borderLeftWidth: 3, paddingLeft: 12 }}><Text style={{ color: theme.colors.foregroundMuted, fontStyle: "italic", lineHeight: 22 }}><InlineMarkdown text={block.text} theme={theme}/></Text></View>;
      if (block.type === "table") {
        const table = markdownTable(block.text);
        const cellWidth = compact ? 140 : 190;
        const renderRow = (cells: string[], rowKey: string, header = false) => <View key={rowKey} style={{ flexDirection: "row", minWidth: table.columnCount * cellWidth }}>
          {Array.from({ length: table.columnCount }, (_, cellIndex) => <View key={cellIndex} style={{ width: cellWidth, borderRightColor: theme.colors.foregroundMuted, borderRightWidth: cellIndex + 1 < table.columnCount ? 1 : 0, borderBottomColor: theme.colors.foregroundMuted, borderBottomWidth: 1, paddingVertical: 8, paddingHorizontal: 10, backgroundColor: header ? theme.colors.surface0 : undefined }}><Text selectable style={{ color: theme.colors.foreground, fontWeight: header ? "700" : "400", lineHeight: 20 }}><InlineMarkdown text={cells[cellIndex] ?? ""} theme={theme}/></Text></View>)}
        </View>;
        return <ScrollView key={index} horizontal showsHorizontalScrollIndicator style={{ borderColor: theme.colors.foregroundMuted, borderWidth: 1, borderRadius: 8 }}>
          <View>{table.header && renderRow(table.header, "header", true)}{table.rows.map((row, rowIndex) => renderRow(row, `row-${rowIndex}`))}</View>
        </ScrollView>;
      }
      if (block.type === "bullet" || block.type === "ordered") return <View key={index} style={{ flexDirection: "row", paddingLeft: 6, gap: 8 }}><Text style={{ color: theme.colors.accent }}>{block.type === "bullet" ? "•" : block.text.split(" ")[0]}</Text><Text style={{ color: theme.colors.foreground, flex: 1, lineHeight: 22 }}><InlineMarkdown text={block.type === "ordered" ? block.text.replace(/^\d+\.\s+/, "") : block.text} theme={theme}/></Text></View>;
      if (block.type.startsWith("h")) return <Text key={index} style={{ color: theme.colors.foreground, fontSize: sizes[block.type], fontWeight: "700", marginTop: index ? 8 : 0 }}><InlineMarkdown text={block.text} theme={theme}/></Text>;
      return <Text key={index} selectable style={{ color: theme.colors.foreground, lineHeight: 23 }}><InlineMarkdown text={block.text} theme={theme}/></Text>;
    })}
  </View>;
}

export function IntentRecordsPanel({ theme, layout, workspaceId, addComposerAttachment }: PluginWorkspacePanelProps) {
  const workspace = useWorkspace(workspaceId, ({ projectId, projectRootPath, projectDisplayName }) => ({ projectId, projectRootPath, projectDisplayName }));
  const list = useRpc(listIntentRecords);
  const read = useRpc(readIntentRecord);
  const getAttachment = useRpc(getIntentRecordAttachment);
  const getInbox = useRpc(getDecisionInbox);
  const [scope, setScope] = useState<"now" | "history">("now");
  const [query, setQuery] = useState("");
  const [items, setItems] = useState<RecordSummary[]>([]);
  const [openRecords, setOpenRecords] = useState<RecordSummary[]>([]);
  const [activePath, setActivePath] = useState<string | null>(null);
  const [documents, setDocuments] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attachmentState, setAttachmentState] = useState<Record<string, "loading" | "attached" | "copied" | "error">>({});
  const [inbox, setInbox] = useState<{ goal: string; lifecycle: string; items: { id: string; action?: string; status: string; reasons: string[]; summary?: string | null; evidence?: string; caller?: string }[] } | null>(null);

  const openInbox = async (goal: string) => {
    if (!workspace) return;
    setLoading(true); setError(null);
    try { setInbox(await getInbox({ paseoProjectId: workspace.projectId, projectRootPath: workspace.projectRootPath, goal })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "Decision Inbox를 불러오지 못했습니다."); }
    finally { setLoading(false); }
  };

  const copyCaller = async (caller: string): Promise<boolean> => {
    const clipboard = (globalThis as unknown as { navigator?: { clipboard?: { writeText(value: string): Promise<void> } } }).navigator?.clipboard;
    if (!clipboard) { setError(`클립보드를 사용할 수 없습니다. 아래 호출자를 직접 복사하세요: ${caller}`); return false; }
    try { await clipboard.writeText(caller); return true; }
    catch { setError(`호출자를 복사하지 못했습니다. 아래 텍스트를 직접 복사하세요: ${caller}`); return false; }
  };

  const attach = async (record: RecordSummary) => {
    if (attachmentState[record.relativePath] === "loading") return;
    setAttachmentState((current) => ({ ...current, [record.relativePath]: "loading" }));
    try {
      if (!addComposerAttachment) {
        const copied = await copyCaller(recordCaller(record));
        setAttachmentState((current) => ({ ...current, [record.relativePath]: copied ? "copied" : "error" }));
        return;
      }
      const item = await getAttachment({ projectId: record.projectId, relativePath: record.relativePath });
      addComposerAttachment({ sourceId: "intent-record", item });
      setAttachmentState((current) => ({ ...current, [record.relativePath]: "attached" }));
    } catch (reason) {
      setAttachmentState((current) => ({ ...current, [record.relativePath]: "error" }));
      setError(reason instanceof Error ? reason.message : "문서를 첨부하지 못했습니다.");
    }
  };

  const refresh = async () => {
    if (!workspace) return;
    setLoading(true); setError(null);
    try {
      const result = await list({ paseoProjectId: workspace.projectId, projectRootPath: workspace.projectRootPath, scope, query });
      setItems(result.items);
    } catch (reason) { setItems([]); setError(reason instanceof Error ? reason.message : "기록을 불러오지 못했습니다."); }
    finally { setLoading(false); }
  };

  useEffect(() => { void refresh(); }, [workspace?.projectId, scope]);

  const open = async (record: RecordSummary) => {
    setOpenRecords((current) => current.some(({ relativePath }) => relativePath === record.relativePath) ? current : [...current, record]);
    setActivePath(record.relativePath); setError(null);
    try {
      const result = await read({ projectId: record.projectId, relativePath: record.relativePath });
      setDocuments((current) => ({ ...current, [record.relativePath]: result.text }));
    }
    catch (reason) { setError(reason instanceof Error ? reason.message : "기록을 열지 못했습니다."); }
  };

  const close = (path: string) => {
    setOpenRecords((current) => current.filter(({ relativePath }) => relativePath !== path));
    if (activePath === path) setActivePath(null);
  };

  const active = openRecords.find(({ relativePath }) => relativePath === activePath);
  const groups = useMemo(() => groupRecords(items, scope), [items, scope]);
  const styles = useMemo(() => ({
    screen: { flex: 1, padding: layout.compact ? 12 : 20, gap: 10, backgroundColor: theme.colors.surface0 },
    row: { flexDirection: "row" as const, gap: 8, flexWrap: "wrap" as const },
    controls: { flexDirection: "row" as const, alignItems: "center" as const, gap: layout.compact ? 6 : 8 },
    tabBar: { flexGrow: 0, flexShrink: 0, height: 36 },
    tabRow: { height: 36, flexDirection: "row" as const, alignItems: "center" as const, gap: 4, borderBottomColor: theme.colors.foregroundMuted, borderBottomWidth: 1, paddingBottom: 5 },
    muted: { color: theme.colors.foregroundMuted }, text: { color: theme.colors.foreground },
    input: { color: theme.colors.foreground, borderColor: theme.colors.foregroundMuted, borderWidth: 1, borderRadius: 8, padding: 10, flex: 1, minWidth: 0 },
    button: { backgroundColor: theme.colors.accent, borderRadius: 8, paddingVertical: 9, paddingHorizontal: 12 },
    buttonText: { color: theme.colors.accentForeground },
    ghost: { borderColor: theme.colors.foregroundMuted, borderWidth: 1, borderRadius: 8, paddingVertical: 9, paddingHorizontal: 12 },
    tab: { height: 30, flexGrow: 0, flexShrink: 0, alignSelf: "center" as const, borderRadius: 6, paddingVertical: 5, paddingLeft: 8, paddingRight: 6, flexDirection: "row" as const, alignItems: "center" as const, gap: 5, maxWidth: layout.compact ? 140 : 220 },
    tabLabel: { fontSize: layout.compact ? 11 : 12, lineHeight: 16, flexShrink: 1 },
    closeTab: { width: 22, height: 22, alignItems: "center" as const, justifyContent: "center" as const, borderRadius: 11 },
    closeTabLabel: { fontSize: 15, lineHeight: 17 },
    activeTab: { backgroundColor: theme.colors.accent },
    group: { borderColor: theme.colors.foregroundMuted, borderWidth: 1, borderRadius: 10, overflow: "hidden" as const },
    groupHeader: { paddingVertical: 11, paddingHorizontal: 13, backgroundColor: theme.colors.surface0, gap: 2 },
    groupTitle: { color: theme.colors.foreground, fontSize: layout.compact ? 15 : 17, fontWeight: "700" as const },
    groupSlug: { color: theme.colors.foregroundMuted, fontSize: 11, fontFamily: "monospace" },
    item: { borderTopColor: theme.colors.foregroundMuted, borderTopWidth: 1, paddingVertical: 10, paddingHorizontal: 13, gap: 4 },
    purpose: { color: theme.colors.accent, fontSize: 12, fontWeight: "700" as const },
    itemTitle: { color: theme.colors.foreground, fontSize: 14 },
    itemMeta: { color: theme.colors.foregroundMuted, fontSize: 11 },
    document: { borderColor: theme.colors.foregroundMuted, borderWidth: 1, borderRadius: 10, padding: layout.compact ? 14 : 22 },
    documentHeader: { flexDirection: "row" as const, alignItems: "center" as const, justifyContent: "space-between" as const, gap: 12, marginBottom: 12 },
    documentHeading: { color: theme.colors.foreground, fontSize: layout.compact ? 16 : 19, fontWeight: "700" as const, flex: 1 },
    error: { color: theme.colors.statusDanger },
  }), [theme, layout.compact]);

  if (!workspace) return <View style={styles.screen}><Text style={styles.error}>Workspace 정보를 사용할 수 없습니다.</Text></View>;
  return <View style={styles.screen}>
    {openRecords.length > 0 && <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.tabBar} contentContainerStyle={styles.tabRow}>
      <Pressable onPress={() => setActivePath(null)} style={[styles.tab, !activePath && styles.activeTab]}><Text numberOfLines={1} style={[styles.tabLabel, !activePath ? styles.buttonText : styles.text]}>기록 목록</Text></Pressable>
      {openRecords.map((record) => <View key={record.relativePath} style={[styles.tab, activePath === record.relativePath && styles.activeTab]}><Pressable onPress={() => setActivePath(record.relativePath)} style={{ flexShrink: 1 }}><Text numberOfLines={1} ellipsizeMode="tail" style={[styles.tabLabel, activePath === record.relativePath ? styles.buttonText : styles.text]}>{record.title}</Text></Pressable><Pressable accessibilityLabel={`${record.title} 탭 닫기`} hitSlop={6} onPress={() => close(record.relativePath)} style={styles.closeTab}><Text style={[styles.closeTabLabel, activePath === record.relativePath ? styles.buttonText : styles.muted]}>×</Text></Pressable></View>)}
    </ScrollView>}
    {error && <Text style={styles.error}>{error}</Text>}
    {inbox ? <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.document}>
      <View style={styles.documentHeader}><View><Text style={styles.documentHeading}>Decision Inbox</Text><Text style={styles.muted}>{inbox.goal} · {inbox.lifecycle}</Text></View><Pressable onPress={() => setInbox(null)} style={styles.ghost}><Text style={styles.text}>목록으로</Text></Pressable></View>
      {inbox.items.length === 0 ? <Text style={styles.muted}>현재 확인할 결정이나 차단 항목이 없습니다.</Text> : inbox.items.map((item) => <View key={item.id} style={styles.item}><Text style={styles.purpose}>{item.action ?? item.id} · {item.status}</Text>{item.summary && <Text style={styles.text}>{item.summary}</Text>}{item.reasons.map((reason) => <Text key={reason} style={styles.muted}>{reason}</Text>)}{item.evidence && <Text style={styles.itemMeta}>{item.evidence}</Text>}{item.caller && <View style={styles.row}><Text selectable style={[styles.text, { fontFamily: "monospace", flex: 1 }]}>{item.caller}</Text><Pressable onPress={() => void copyCaller(item.caller!)} style={styles.button}><Text style={styles.buttonText}>호출자 복사</Text></Pressable></View>}</View>)}
    </ScrollView> : active ? <ScrollView style={{ flex: 1 }} contentContainerStyle={styles.document}>
      <View style={styles.documentHeader}>
        <View style={{ flex: 1, minWidth: 0 }}><Text numberOfLines={2} style={styles.documentHeading}>{active.title}</Text><Text style={styles.muted}>{active.relativePath.replace(`projects/${active.projectId}/`, "")} · {active.updated ?? active.created ?? "날짜 없음"}</Text></View>
        <Pressable accessibilityRole="button" accessibilityLabel={`${active.title} ${addComposerAttachment ? "문서 첨부" : "호출자 복사"}`} disabled={attachmentState[active.relativePath] === "loading" || attachmentState[active.relativePath] === "attached"} onPress={() => void attach(active)} style={attachmentState[active.relativePath] === "attached" || attachmentState[active.relativePath] === "copied" ? styles.ghost : styles.button}><Text style={attachmentState[active.relativePath] === "attached" || attachmentState[active.relativePath] === "copied" ? styles.text : styles.buttonText}>{attachmentState[active.relativePath] === "loading" ? (addComposerAttachment ? "첨부 중…" : "복사 중…") : attachmentState[active.relativePath] === "attached" ? "첨부됨" : attachmentState[active.relativePath] === "copied" ? "호출자 복사됨" : attachmentState[active.relativePath] === "error" ? (addComposerAttachment ? "다시 첨부" : "다시 복사") : addComposerAttachment ? "첨부" : "호출자 복사"}</Text></Pressable>
      </View>
      {!addComposerAttachment && <Text selectable style={[styles.itemMeta, { fontFamily: "monospace", marginBottom: 10 }]}>{recordCaller(active)}</Text>}
      {documents[active.relativePath] ? <MarkdownDocument markdown={documents[active.relativePath]} theme={theme} compact={layout.compact}/> : <ActivityIndicator color={theme.colors.accent}/>}
    </ScrollView> : <>
      <View style={styles.controls}>{(["now", "history"] as const).map((value) => <Pressable key={value} onPress={() => setScope(value)} style={value === scope ? styles.button : styles.ghost}><Text style={value === scope ? styles.buttonText : styles.text}>{value === "now" ? "NOW" : "History"}</Text></Pressable>)}<TextInput accessibilityLabel="SKIP 기록 검색" placeholder="설계 제목, 폴더명 또는 문서 목적" placeholderTextColor={theme.colors.foregroundMuted} value={query} onChangeText={setQuery} onSubmitEditing={() => void refresh()} style={styles.input}/><Pressable accessibilityRole="button" onPress={() => void refresh()} style={styles.button}><Text style={styles.buttonText}>검색</Text></Pressable></View>
      {loading && <ActivityIndicator color={theme.colors.accent}/>}
      <Text style={styles.muted}>기록을 누르면 위에 독립 문서 탭으로 열립니다. 열린 문서는 제목 옆에서 정확히 첨부할 수 있습니다.</Text>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ gap: 10, paddingBottom: 24 }}>
        {items.length === 0 && !loading && !error && <Text style={styles.muted}>{scope === "now" ? "NOW 기록이 없습니다." : "조건에 맞는 역사 기록이 없습니다."}</Text>}
        {groups.map((group) => <View key={group.key} style={styles.group}>
          <View style={styles.groupHeader}><View style={styles.row}><View style={{ flex: 1 }}><Text style={styles.groupTitle}>{group.title}</Text>{group.slug && <Text style={styles.groupSlug}>{group.slug}</Text>}</View>{group.slug && <Pressable onPress={() => void openInbox(group.slug!)} style={styles.ghost}><Text style={styles.text}>Decision Inbox</Text></Pressable>}</View></View>
          {group.records.map((record) => <Pressable key={record.relativePath} onPress={() => void open(record)} style={styles.item}>
            <Text style={styles.purpose}>{ARTIFACT_PURPOSE[record.artifact] ?? record.artifact}</Text>
            <Text numberOfLines={2} style={styles.itemTitle}>{record.title}</Text>
            <Text style={styles.itemMeta}>{[record.status, record.updated ?? record.created ?? "날짜 없음"].filter(Boolean).join(" · ")}</Text>
          </Pressable>)}
        </View>)}
      </ScrollView>
    </>}
  </View>;
}
