import assert from "node:assert/strict";
import { mkdtemp, mkdir, symlink, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { decisionInbox, exactRecordAttachment, listRecords, parsePaseoBindings, readRecord } from "./records.server";
import { recordCaller } from "./records.caller";

test("builds portable record callers for direct-attachment fallback", () => {
  assert.equal(recordCaller({ projectId: "demo", scope: "history", goal: "checkout", artifact: "system_design" }), "$skip --project demo --goal checkout --artifacts system-design");
  assert.equal(recordCaller({ projectId: "demo", scope: "now", goal: "checkout", artifact: "goal" }), "$skip --project demo --now --goal checkout");
});

test("parses only paseo bindings", () => {
  const bindings = parsePaseoBindings("version: 2\nbindings:\n  paseo:\n    prj_123: quickhack\nprojects:\n  ignored: value\n");
  assert.equal(bindings.get("prj_123"), "quickhack");
  assert.equal(bindings.has("ignored"), false);
});

test("lists NOW and reads a stable snapshot", async () => {
  const root = await mkdtemp(join(tmpdir(), "intent-records-"));
  process.env.INTENT_TO_CODE_RECORD_ROOT = root;
  await mkdir(join(root, "projects", "demo", "NOW"), { recursive: true });
  await writeFile(join(root, "projects", "demo", "project.yaml"), "project_id: demo\ndisplay_name: Demo\n");
  await writeFile(join(root, "projects", "demo", "NOW", "index.md"), "---\nupdated: 2026-08-26\n---\n# Current truth\nBody\n");
  const items = await listRecords("demo", "now", "truth");
  assert.equal(items.length, 1);
  const result = await readRecord("demo", items[0]!.relativePath);
  assert.match(result.text, /Current truth/);
  const attachment = await exactRecordAttachment("demo", items[0]!.relativePath);
  assert.equal(attachment.identifier, "demo:NOW/index.md");
  assert.match(attachment.text, /SKIP record snapshot/);
  assert.match(attachment.text, /Current truth/);
});

test("uses frontmatter title and searches Korean artifact purpose", async () => {
  const root = await mkdtemp(join(tmpdir(), "intent-records-"));
  process.env.INTENT_TO_CODE_RECORD_ROOT = root;
  await mkdir(join(root, "projects", "demo", "features", "os-dependency"), { recursive: true });
  await writeFile(join(root, "projects", "demo", "project.yaml"), "project_id: demo\ndisplay_name: Demo\n");
  await writeFile(join(root, "projects", "demo", "features", "os-dependency", "prd.md"), "---\ntitle: 운영체제 의존성 구조 요구사항\nupdated: 2026-08-26\n---\n# 한 문장 목표\nBody\n");
  const items = await listRecords("demo", "history", "제품 목표");
  assert.equal(items.length, 1);
  assert.equal(items[0]?.title, "운영체제 의존성 구조 요구사항");
  assert.equal(items[0]?.goal, "os-dependency");
});

test("parses title and dates from legacy CRLF frontmatter", async () => {
  const root = await mkdtemp(join(tmpdir(), "intent-records-"));
  process.env.INTENT_TO_CODE_RECORD_ROOT = root;
  await mkdir(join(root, "projects", "demo", "features", "legacy"), { recursive: true });
  await writeFile(join(root, "projects", "demo", "project.yaml"), "project_id: demo\ndisplay_name: Demo\n");
  await writeFile(join(root, "projects", "demo", "features", "legacy", "impact.md"), "---\r\ntitle: 레거시 기능 영향 분석\r\nstatus: draft\r\ncreated: 2026-08-10\r\nupdated: 2026-08-11\r\n---\r\n# 1. 조사 목표와 경계\r\n");
  const items = await listRecords("demo", "history", "레거시");
  assert.equal(items[0]?.title, "레거시 기능 영향 분석");
  assert.equal(items[0]?.created, "2026-08-10");
  assert.equal(items[0]?.updated, "2026-08-11");
});

test("lists history records newest first and puts undated records last", async () => {
  const root = await mkdtemp(join(tmpdir(), "intent-records-"));
  process.env.INTENT_TO_CODE_RECORD_ROOT = root;
  const feature = join(root, "projects", "demo", "features", "ordering");
  await mkdir(feature, { recursive: true });
  await writeFile(join(root, "projects", "demo", "project.yaml"), "project_id: demo\ndisplay_name: Demo\n");
  await writeFile(join(feature, "impact.md"), "---\nupdated: 2026-08-20\n---\n# Older\n");
  await writeFile(join(feature, "prd.md"), "---\ncreated: 2026-08-27\n---\n# Newer\n");
  await writeFile(join(feature, "tasks.md"), "# Undated\n");

  const items = await listRecords("demo", "history");
  assert.deepEqual(items.map(({ title }) => title), ["Newer", "Older", "Undated"]);
});

test("rejects traversal and symlink escape", async () => {
  const root = await mkdtemp(join(tmpdir(), "intent-records-"));
  process.env.INTENT_TO_CODE_RECORD_ROOT = root;
  await mkdir(join(root, "projects", "demo", "NOW"), { recursive: true });
  await writeFile(join(root, "projects", "demo", "project.yaml"), "project_id: demo\n");
  await symlink("/etc/hosts", join(root, "projects", "demo", "NOW", "escape.md"));
  await assert.rejects(() => readRecord("demo", "projects/demo/NOW/../../outside.md"), /허용되지 않은/);
  await assert.rejects(() => readRecord("demo", "projects/demo/NOW/escape.md"), /심볼릭 링크/);
});

test("reads Decision Inbox through the bounded SKIP runtime adapter", async () => {
  const root = await mkdtemp(join(tmpdir(), "intent-records-"));
  process.env.INTENT_TO_CODE_RECORD_ROOT = root;
  await mkdir(join(root, "projects", "demo", "features", "goal"), { recursive: true });
  await writeFile(join(root, "projects", "demo", "project.yaml"), "project_id: demo\ndisplay_name: Demo\n");
  const runtime = join(root, "runtime.py");
  await writeFile(runtime, "import json\nprint(json.dumps({'schema':'decision-inbox/v1','project_id':'demo','goal':'goal','lifecycle':'active','items':[]}))\n");
  process.env.SKIP_RUNTIME_SCRIPT = runtime;
  const result = await decisionInbox("demo", "goal");
  assert.equal(result.schema, "decision-inbox/v1");
  assert.equal(result.goal, "goal");
});
