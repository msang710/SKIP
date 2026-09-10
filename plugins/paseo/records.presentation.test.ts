import assert from "node:assert/strict";
import test from "node:test";
import { projectReading, statusLabel, type RecordMeta } from "./records.presentation";
const now: RecordMeta = { projectId: "demo", relativePath: "projects/demo/NOW/goals/search.md", title: "검색", scope: "now", goal: "search", artifact: "search", status: "partially-verified" };
test("NOW-only projection attributes source lines and separates mixed validation gaps", () => {
  const reading = projectReading([{ record: now, text: "---\nstatus: partially-verified\n---\n# 검색\n검색을 구현했습니다.\n## 검증\n- Python 126개 통과\n- 테스트 3개 미실행, 나머지는 통과\n- 화면 확인 예정\n" }]);
  assert.equal(reading.summary[0].line, 5);
  assert.equal(reading.summary[0].path, now.relativePath);
  assert.equal(reading.checks.length, 1);
  assert.equal(reading.gaps.length, 2);
});
test("approved historical plan never becomes current implementation or passed validation", () => {
  const record = { ...now, scope: "history" as const, status: "approved" };
  const reading = projectReading([{ record, text: "# 구현 계획\n구현 완료\n테스트 PASS\n## 결정 D-001\n기존 방식을 유지한다.\n" }]);
  assert.equal(statusLabel(record), "과거 기록");
  assert.equal(reading.checks.length, 0); assert.equal(reading.summary.length, 0);
  assert.equal(reading.decisions.length, 2);
  assert.equal(reading.decisions[1].text, "기존 방식을 유지한다."); assert.equal(reading.warnings.length, 1);
});
test("missing status and conflicting current records remain explicit", () => {
  assert.equal(statusLabel({ ...now, status: undefined }), "현재 상태 확인 필요");
  const reading = projectReading([{ record: now, text: "# A" }, { record: { ...now, status: "verified" }, text: "# B" }]);
  assert.match(reading.warnings[0], /상태가 다릅니다/);
});
test("example code and frontmatter are not rendered as verified evidence", () => {
  const reading = projectReading([{ record: now, text: "---\nresult: PASS\n---\n# 상태\n```text\nPASS\n```\n검증 필요\n" }]);
  assert.equal(reading.checks.length, 0); assert.equal(reading.gaps.length, 1);
});
test("decision reasons under subheadings retain provenance without unrelated sections", () => {
  const reading = projectReading([{ record: { ...now, scope: "history" }, text: "# 계획\n## 결정 D-001\n유지\n### 이유\n재고 중복 방지\n## 설계\nlease 구현\n" }]);
  assert.ok(reading.decisions.some(d => d.text === "재고 중복 방지" && d.line === 5));
  assert.ok(!reading.decisions.some(d => d.text.includes("lease")));
});
