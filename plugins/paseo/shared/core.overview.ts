/** Presentation of native Core status. No historical document parsing or inferred goals. */
export function overview(status: any, inbox: any[], goals: any[]) {
  const work = (status?.work_items ?? []).filter((w: any) => w.lifecycle === "active");
  const pending = inbox.filter(c => !c.selection || c.selection_stale);
  const decisions = pending.filter(c => c.action_state !== "needs_options" && c.children?.options?.length >= 2);
  return {
    goals: goals.filter(g => g.lifecycle === "active"),
    decisions,
    incompleteDecisions: pending.filter(c => c.action_state === "needs_options" || !c.children?.options || c.children.options.length < 2),
    work: work.map((w: any) => ({ ...w, displayState: w.origin ? "당시 작업 기록 · 현재 상태 확인 필요" :
      (status.remaining ?? []).some((r: any) => r.work_id === w.id) ? "검증이 남아 있음" : (w.children?.checks ?? []).some((c: any) => c.required) ? "필수 검증 기록 확인됨" : "검증 조건 확인 필요" })),
    checks: (status?.checks ?? []).filter((c: any) => !c.origin),
    historicalChecks: (status?.checks ?? []).filter((c: any) => c.origin).length,
    empty: !goals.length && !work.length && !decisions.length,
  };
}
export function brief(value: string, maximum = 150) {
  const line = (value ?? "").split(/\r?\n/).map(v => v.replace(/^\s*(?:#{1,6}\s+|[-*]\s+)/, "").trim()).find(Boolean) ?? "검증 기록";
  return line.length > maximum ? line.slice(0, maximum) + "…" : line;
}

/** Current source evidence and historical/unverified facts must not share a status. */
export function nowOverview(status: any) {
  const facts = status?.facts ?? [];
  const current = (f: any) => f.freshness === "current" && !f.origin;
  const activeWork = new Set((status?.work_items ?? []).filter((w: any) => w.lifecycle === "active" && !w.origin).map((w: any) => w.id));
  return {
    facts: facts.filter(current),
    previousFacts: facts.filter((f: any) => !current(f)),
    checks: (status?.checks ?? []).filter((c: any) => !c.origin),
    remaining: (status?.remaining ?? []).filter((r: any) => activeWork.has(r.work_id)),
  };
}

/** List labels use Core's current selection, never historical approval text. */
export function decisionSummary(record: any): string {
  if (record.selection_state === "revoked") return "미결정 · 선택 철회됨";
  if (record.selection_stale || record.selection_state === "stale") return "재확인 필요 · 결정 내용 변경됨";
  if (record.selection_state === "selected" && record.selected_option?.label) return `결정됨 · ${record.selected_option.label}`;
  if (record.action_state === "needs_options") return "미결정 · 선택지 정리 필요";
  return "미결정";
}
