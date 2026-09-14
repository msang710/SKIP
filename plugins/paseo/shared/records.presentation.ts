/** Read-only projections. Text is attributed to records, never a new verification. */
export type RecordMeta = { projectId: string; relativePath: string; title: string; scope: "now" | "history"; goal?: string; status?: string; updated?: string; created?: string; verifiedAt?: string; sourceRevision?: string; artifact: string };
export type Excerpt = { text: string; path: string; line: number };
export type Reading = { summary: Excerpt[]; checks: Excerpt[]; gaps: Excerpt[]; decisions: Excerpt[]; warnings: string[] };
export function statusLabel(record: RecordMeta): string {
  if (record.scope !== "now") return "과거 기록";
  const labels: Record<string, string> = { "partially-verified": "일부 미검증", verified: "검증됨 · 기록 기준", implemented: "구현됨 · 기록 기준", blocked: "진행 막힘", stale: "재확인 필요", fail: "검증 실패", not_run: "미실행", evidence_pending: "근거 확인 필요" };
  return labels[(record.status ?? "").toLowerCase()] ?? "현재 상태 확인 필요";
}
export function projectReading(docs: { record: RecordMeta; text: string }[]): Reading {
  const result: Reading = { summary: [], checks: [], gaps: [], decisions: [], warnings: [] };
  const now = docs.filter(d => d.record.scope === "now");
  if (new Set(now.map(d => d.record.status).filter(Boolean)).size > 1) result.warnings.push("기록 간 상태가 다릅니다. 원문 확인이 필요합니다.");
  for (const { record, text } of docs) {
    let section = "", code = false, metadata = text.startsWith("---\n") || text.startsWith("---\r\n");
    let summaryCount = 0, decisionDepth = 0;
    text.replaceAll("\r\n", "\n").split("\n").forEach((raw, index) => {
      if (metadata) { if (index > 0 && raw === "---") metadata = false; return; }
      if (/^\s*```/.test(raw)) { code = !code; return; }
      if (code) return;
      const heading = raw.match(/^#{1,6}\s+(.+)/);
      if (heading) {
        section = heading[1];
        const depth = raw.match(/^#+/)![0].length;
        if (decisionDepth && depth <= decisionDepth) decisionDepth = 0;
        if (/결정|decision|\bD-(?:[A-Z]+-)?\d/i.test(section)) decisionDepth = depth;
        if (decisionDepth) result.decisions.push({ text: section, path: record.relativePath, line: index + 1 });
        return;
      }
      const text = raw.replace(/^\s*[-*]\s+/, "").trim();
      if (!text || /^\|?\s*[-:|]+\s*$/.test(text)) return;
      const item = { text, path: record.relativePath, line: index + 1 };
      if (decisionDepth) result.decisions.push(item);
      if (record.scope !== "now") return; // A historical plan is never implementation evidence.
      const gap = /NOT_RUN|EVIDENCE_PENDING|BLOCKED|STALE|FAIL|미검증|미실행|미확인|확인 필요|실패|아직|NOT VERIFIED/i.test(text) || /미검증|미확인|남은|한계|gaps|not verified/i.test(section);
      if (gap) result.gaps.push(item);
      else if (/예정|계획|해야|필요|will |should |must /i.test(text)) result.gaps.push(item);
      else if (/통과|확인했|검증했|\bPASS(?:ED)?\b|✓|✔/i.test(text)) result.checks.push(item);
      else if (summaryCount < 2 && !/증거|source|metadata|evidence|결정|decision/i.test(section) && !/^\||^[/]|^https?:/.test(text)) { result.summary.push(item); summaryCount++; }
    });
  }
  if (!now.length) result.warnings.push("현재 상태 기록이 없습니다. 과거 계획을 구현 결과로 표시하지 않습니다.");
  return result;
}
