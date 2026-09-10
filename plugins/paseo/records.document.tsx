import { Fragment, useRef, useState } from "react";
import { Pressable, ScrollView, Text, View } from "react-native";
import type { PluginTheme } from "@getpaseo/plugin";
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

export function MarkdownDocument({ markdown, theme, compact }: { markdown: string; theme: PluginTheme; compact: boolean }) {
  const scroll = useRef<ScrollView>(null);
  const [showContents, setShowContents] = useState(false);
  const positions = useRef<Record<number, number>>({});
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
  return <ScrollView ref={scroll} style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 36 }}><View style={{ width: "100%", maxWidth: 720, alignSelf: "center", gap: 16 }}>
    {blocks.filter(b => /^h[1-4]$/.test(b.type)).length > 3 && <View style={{ gap: 8, paddingVertical: 12 }}><Pressable accessibilityRole="button" onPress={() => setShowContents(value => !value)}><Text style={{ color: theme.colors.foregroundMuted }}>{showContents ? "목차 접기" : "목차 보기"}</Text></Pressable>{showContents ? blocks.map((b, i) => /^h[1-4]$/.test(b.type) ? <Pressable key={i} accessibilityRole="button" onPress={() => scroll.current?.scrollTo({ y: positions.current[i] ?? 0, animated: true })}><Text style={{ color: theme.colors.accent, fontSize: 14 }}>{b.text}</Text></Pressable> : null) : null}</View>}
    {blocks.map((block, index) => {
      if (block.type === "rule") return <View key={index} style={{ height: 1, backgroundColor: theme.colors.foregroundMuted, opacity: 0.35, marginVertical: 4 }}/>;
      if (block.type === "code") return <ScrollView key={index} horizontal><View style={{ backgroundColor: theme.colors.surface0, borderColor: theme.colors.foregroundMuted, borderWidth: 1, borderRadius: 8, padding: 12 }}><Text style={{ color: theme.colors.foregroundMuted, fontSize: 11 }}>{block.language}</Text><Text selectable style={{ color: theme.colors.foreground, fontFamily: "monospace", lineHeight: 20 }}>{block.text}</Text></View></ScrollView>;
      if (block.type === "quote") return <View key={index} style={{ borderLeftColor: theme.colors.accent, borderLeftWidth: 3, paddingLeft: 12 }}><Text style={{ color: theme.colors.foregroundMuted, fontStyle: "italic", fontSize: 16, lineHeight: 27 }}><InlineMarkdown text={block.text} theme={theme}/></Text></View>;
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
      if (block.type === "bullet" || block.type === "ordered") return <View key={index} style={{ flexDirection: "row", paddingLeft: 6, gap: 8 }}><Text style={{ color: theme.colors.accent }}>{block.type === "bullet" ? "•" : block.text.split(" ")[0]}</Text><Text style={{ color: theme.colors.foreground, flex: 1, fontSize: 16, lineHeight: 27 }}><InlineMarkdown text={block.type === "ordered" ? block.text.replace(/^\d+\.\s+/, "") : block.text} theme={theme}/></Text></View>;
      if (block.type.startsWith("h")) return <Text onLayout={event => { positions.current[index] = event.nativeEvent.layout.y; }} key={index} style={{ color: theme.colors.foreground, fontSize: sizes[block.type], fontWeight: "700", marginTop: index ? 8 : 0 }}><InlineMarkdown text={block.text} theme={theme}/></Text>;
      return <Text key={index} selectable style={{ color: theme.colors.foreground, fontSize: 16, lineHeight: 27 }}><InlineMarkdown text={block.text} theme={theme}/></Text>;
    })}
  </View></ScrollView>;
}
