import { lstat, readFile, realpath, stat } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { homedir, platform } from "node:os";
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import type { PluginAttachmentItem } from "@getpaseo/plugin/server";

const MAX_DOCUMENT_BYTES = 200 * 1024;
const MAX_RESULTS = 250;
const execFileAsync = promisify(execFile);
const SLUG = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const ARTIFACT_SEARCH_LABELS: Record<string, string> = {
  impact: "영향 분석 조사",
  prd: "제품 목표 요구사항",
  user_stories: "사용자 스토리",
  system_design: "시스템 설계",
  tasks: "구현 계획 작업",
  index: "현재 상태 안내",
  system: "현재 시스템",
  validation: "검증 상태",
};

export type RecordScope = "now" | "history";
export type RecordSummary = {
  projectId: string;
  scope: RecordScope;
  goal?: string;
  artifact: string;
  relativePath: string;
  title: string;
  status?: string;
  verifiedAt?: string;
  created?: string;
  updated?: string;
  sourceRevision?: string;
  byteLength: number;
};

export class IntentRecordError extends Error {
  constructor(readonly code: string, message: string) {
    super(message);
  }
}

function platformRoot(kind: "data" | "config"): string {
  if (platform() === "win32") {
    const key = kind === "data" ? "LOCALAPPDATA" : "APPDATA";
    const value = process.env[key];
    if (!value) throw new IntentRecordError("HOST_PATH_UNAVAILABLE", `${key} is unavailable`);
    return value;
  }
  if (platform() === "darwin") return join(homedir(), "Library", "Application Support");
  return kind === "data" ? process.env.XDG_DATA_HOME ?? join(homedir(), ".local", "share")
    : process.env.XDG_CONFIG_HOME ?? join(homedir(), ".config");
}

export function recordRoot(): string {
  return resolve(process.env.INTENT_TO_CODE_RECORD_ROOT ?? join(platformRoot("data"), "SKIP"));
}

function registryPath(): string {
  return resolve(process.env.INTENT_TO_CODE_WORKSPACE_REGISTRY ?? join(platformRoot("config"), "intent-to-code", "workspaces.yaml"));
}

function assertSlug(value: string, label: string): string {
  if (!SLUG.test(value)) throw new IntentRecordError("INVALID_ID", `${label} 형식이 잘못되었습니다.`);
  return value;
}

function parseScalarYaml(text: string): Record<string, string> {
  if (text.trimStart().startsWith("{")) {
    const value = JSON.parse(text);
    if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid project metadata");
    return value;
  }
  const result: Record<string, string> = {};
  for (const line of text.split(/\r?\n/)) {
    const match = line.match(/^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*?)\s*$/);
    if (match && match[2]) result[match[1]] = match[2].replace(/^['"]|['"]$/g, "");
  }
  return result;
}

export function parsePaseoBindings(text: string): Map<string, string> {
  const bindings = new Map<string, string>();
  if (text.trimStart().startsWith("{")) {
    const value = JSON.parse(text);
    for (const [id, project] of Object.entries(value.bindings?.paseo ?? {})) {
      if (typeof project !== "string" || !SLUG.test(project)) throw new Error("Invalid Paseo project binding");
      bindings.set(id, project);
    }
    return bindings;
  }
  const lines = text.split(/\r?\n/);
  let inBindings = false;
  let inPaseo = false;
  for (const line of lines) {
    if (/^bindings:\s*$/.test(line)) { inBindings = true; inPaseo = false; continue; }
    if (inBindings && /^  paseo:\s*$/.test(line)) { inPaseo = true; continue; }
    const match = inPaseo ? line.match(/^    ([A-Za-z0-9_-]+):\s*([a-z0-9-]+)\s*$/) : null;
    if (match) { bindings.set(match[1], match[2]); continue; }
    if (inPaseo && /^\S|^  \S/.test(line)) { inBindings = false; inPaseo = false; }
  }
  return bindings;
}

async function declaredProject(projectId: string): Promise<{ projectId: string; displayName: string }> {
  assertSlug(projectId, "프로젝트 ID");
  const path = await containedPath(join("projects", projectId, "project.yaml"), false, [".yaml"]);
  const fields = parseScalarYaml(await readFile(path, "utf8"));
  if (fields.project_id !== projectId) throw new IntentRecordError("IDENTITY_CONFLICT", "기록 프로젝트 ID가 일치하지 않습니다.");
  return { projectId, displayName: fields.display_name ?? projectId };
}

export async function resolveProject(paseoProjectId: string, _projectRootPath: string) {
  const bindings = parsePaseoBindings(await readFile(registryPath(), "utf8"));
  const projectId = bindings.get(paseoProjectId);
  if (!projectId) throw new IntentRecordError("PROJECT_UNBOUND", "이 Paseo 프로젝트에 연결된 SKIP 기록이 없습니다.");
  return declaredProject(projectId);
}

async function containedPath(relativePath: string, requireMarkdown = true, extensions = [".md"]): Promise<string> {
  if (isAbsolute(relativePath) || relativePath.split(/[\\/]+/).includes("..")) {
    throw new IntentRecordError("PATH_ESCAPE", "허용되지 않은 기록 경로입니다.");
  }
  const root = await realpath(recordRoot());
  const candidate = resolve(root, relativePath);
  const rel = relative(root, candidate);
  if (!rel || rel.startsWith(`..${sep}`) || rel === ".." || isAbsolute(rel)) {
    throw new IntentRecordError("PATH_ESCAPE", "허용되지 않은 기록 경로입니다.");
  }
  if (!extensions.includes(extname(candidate))) throw new IntentRecordError("FILE_TYPE", "허용되지 않은 기록 형식입니다.");
  const info = await lstat(candidate);
  if (info.isSymbolicLink()) throw new IntentRecordError("PATH_ESCAPE", "심볼릭 링크 기록은 열 수 없습니다.");
  const canonical = await realpath(candidate);
  const canonicalRel = relative(root, canonical);
  if (canonicalRel.startsWith(`..${sep}`) || canonicalRel === ".." || isAbsolute(canonicalRel)) {
    throw new IntentRecordError("PATH_ESCAPE", "기록 루트 밖의 파일은 열 수 없습니다.");
  }
  if (requireMarkdown && extname(canonical) !== ".md") throw new IntentRecordError("FILE_TYPE", "Markdown 기록만 열 수 있습니다.");
  return canonical;
}

function frontmatter(text: string): Record<string, string> {
  const normalized = text.replaceAll("\r\n", "\n");
  if (!normalized.startsWith("---\n")) return {};
  const end = normalized.indexOf("\n---\n", 4);
  return end < 0 ? {} : parseScalarYaml(normalized.slice(4, end));
}

function titleOf(text: string, fallback: string): string {
  const heading = text.match(/^#\s+(.+)$/m)?.[1]?.trim();
  return heading || fallback;
}

async function summary(projectId: string, relativePath: string, size?: number): Promise<RecordSummary> {
  const path = await containedPath(relativePath);
  const info = size === undefined ? await stat(path) : { size };
  const text = await readFile(path, "utf8");
  const meta = frontmatter(text);
  const segments = relativePath.split("/");
  const now = segments[2] === "NOW";
  const filename = segments.at(-1)?.replace(/\.md$/, "") ?? "record";
  return {
    projectId,
    scope: now ? "now" : "history",
    goal: now && segments[3] === "goals" ? filename : (!now ? segments[3] : undefined),
    artifact: filename,
    relativePath,
    title: meta.title ?? titleOf(text, filename),
    status: meta.status,
    created: meta.created,
    updated: meta.updated,
    sourceRevision: meta.verified_revision ?? meta.source_revision,
    verifiedAt: meta.verified_at,
    byteLength: info.size,
  };
}

async function markdownFiles(directory: string): Promise<string[]> {
  const { readdir } = await import("node:fs/promises");
  const result: string[] = [];
  async function visit(path: string) {
    let entries;
    try { entries = await readdir(path, { withFileTypes: true }); } catch { return; }
    for (const entry of entries) {
      const target = join(path, entry.name);
      if (entry.isSymbolicLink()) continue;
      if (entry.isDirectory()) await visit(target);
      else if (entry.isFile() && entry.name.endsWith(".md")) result.push(target);
    }
  }
  await visit(directory);
  return result;
}

export async function listRecords(projectId: string, scope: RecordScope, query = "") {
  await declaredProject(projectId);
  const baseRelative = join("projects", projectId, scope === "now" ? "NOW" : "features");
  const base = resolve(recordRoot(), baseRelative);
  const words = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const files = await markdownFiles(base);
  const items: RecordSummary[] = [];
  for (const file of files.slice(0, MAX_RESULTS * 2)) {
    const rel = relative(recordRoot(), file).split(sep).join("/");
    const item = await summary(projectId, rel);
    const haystack = `${item.relativePath} ${item.title} ${item.goal ?? ""} ${item.artifact} ${ARTIFACT_SEARCH_LABELS[item.artifact] ?? ""}`.toLowerCase();
    if (words.every((word) => haystack.includes(word))) items.push(item);
    if (items.length >= MAX_RESULTS) break;
  }
  items.sort((a, b) => (b.updated ?? b.created ?? "").localeCompare(a.updated ?? a.created ?? "") || a.relativePath.localeCompare(b.relativePath));
  return items;
}

export async function readRecord(projectId: string, relativePath: string) {
  const expectedPrefix = `projects/${assertSlug(projectId, "프로젝트 ID")}/`;
  if (!relativePath.startsWith(expectedPrefix)) throw new IntentRecordError("PROJECT_MISMATCH", "다른 프로젝트의 기록은 열 수 없습니다.");
  const path = await containedPath(relativePath);
  for (let attempt = 0; attempt < 2; attempt += 1) {
    const before = await stat(path);
    if (before.size > MAX_DOCUMENT_BYTES) throw new IntentRecordError("TOO_LARGE", "200 KiB를 넘는 기록은 첨부할 수 없습니다.");
    const text = await readFile(path, "utf8");
    const after = await stat(path);
    if (before.size === after.size && before.mtimeMs === after.mtimeMs) {
      return { record: await summary(projectId, relativePath, after.size), text };
    }
  }
  throw new IntentRecordError("READ_CONFLICT", "읽는 동안 기록이 변경되었습니다. 다시 시도하세요.");
}

async function allProjectIds(): Promise<string[]> {
  const { readdir } = await import("node:fs/promises");
  const projects = join(recordRoot(), "projects");
  const entries = await readdir(projects, { withFileTypes: true });
  return entries.filter((entry) => entry.isDirectory() && SLUG.test(entry.name)).map((entry) => entry.name).sort();
}

export function attachment(record: RecordSummary, text: string): PluginAttachmentItem {
  const portable = `${record.projectId}:${record.relativePath.replace(`projects/${record.projectId}/`, "")}`;
  return {
    id: `${record.projectId}:${record.relativePath}:${record.updated ?? record.created ?? "undated"}`,
    identifier: portable,
    title: record.title,
    subtitle: [record.scope.toUpperCase(), record.updated ?? record.created, record.status].filter(Boolean).join(" · "),
    url: `https://local.skip.invalid/records/${encodeURIComponent(record.projectId)}/${encodeURIComponent(record.relativePath)}`,
    text: [
      "SKIP record snapshot",
      `Project: ${record.projectId}`,
      `Path: ${record.relativePath.replace(`projects/${record.projectId}/`, "")}`,
      `Updated: ${record.updated ?? "unknown"}`,
      `Source revision: ${record.sourceRevision ?? "see document metadata"}`,
      "",
      text,
    ].join("\n"),
    resourceType: "SKIP record",
  };
}

export async function exactRecordAttachment(projectId: string, relativePath: string): Promise<PluginAttachmentItem> {
  const read = await readRecord(projectId, relativePath);
  return attachment(read.record, read.text);
}

export async function searchRecordAttachments(query: string): Promise<{ items: PluginAttachmentItem[] }> {
  const tokens = query.trim().split(/\s+/).filter(Boolean);
  const projectToken = tokens.find((token) => token.startsWith("project:"));
  const selectedProject = projectToken?.slice("project:".length);
  if (selectedProject) assertSlug(selectedProject, "프로젝트 ID");
  const search = tokens.filter((token) => token !== projectToken).join(" ");
  const ids = selectedProject ? [selectedProject] : await allProjectIds();
  const summaries: RecordSummary[] = [];
  for (const projectId of ids) {
    for (const scope of ["now", "history"] as const) {
      try { summaries.push(...await listRecords(projectId, scope, search)); } catch (error) {
        if (selectedProject) throw error;
      }
    }
  }
  const items: PluginAttachmentItem[] = [];
  for (const record of summaries.slice(0, 50)) {
    try {
      const read = await readRecord(record.projectId, record.relativePath);
      items.push(attachment(read.record, read.text));
    } catch (error) {
      if (!(error instanceof IntentRecordError) || error.code !== "TOO_LARGE") throw error;
    }
  }
  return { items };
}

export async function decisionInbox(projectId: string, goal: string) {
  await declaredProject(projectId);
  assertSlug(goal, "목표 ID");
  const script = process.env.SKIP_RUNTIME_SCRIPT ?? join(homedir(), ".agents", "skills", "skip", "scripts", "intent_context.py");
  try {
    const { stdout } = await execFileAsync("python3", [script, "inbox", "--record-root", recordRoot(), "--project", projectId, "--goal", goal], {
      timeout: 8_000,
      maxBuffer: 512 * 1024,
      env: { ...process.env, PYTHONIOENCODING: "utf-8" },
    });
    const value = JSON.parse(stdout);
    if (value.schema !== "decision-inbox/v1" || value.project_id !== projectId || value.goal !== goal || !Array.isArray(value.items)) {
      throw new IntentRecordError("RUNTIME_CONTRACT", "SKIP runtime 응답 계약이 일치하지 않습니다.");
    }
    return value;
  } catch (error) {
    if (error instanceof IntentRecordError) throw error;
    throw new IntentRecordError("CAPABILITY_UNAVAILABLE", "Decision Inbox runtime을 사용할 수 없습니다.");
  }
}

export async function readGroup(projectId: string, paths: string[]) {
  if (!paths.length || paths.length > 24) throw new IntentRecordError("LIMIT", "한 번에 최대 24개 문서를 읽을 수 있습니다.");
  const documents: Awaited<ReturnType<typeof readRecord>>[] = [];
  const errors: { path: string; message: string }[] = [];
  let group: string | undefined;
  for (const path of [...new Set(paths)]) {
    try {
      const result = await readRecord(projectId, path);
      const key = result.record.goal ?? "__project__";
      if (group !== undefined && group !== key) throw new IntentRecordError("GROUP_MISMATCH", "다른 작업의 기록입니다.");
      group = key;
      documents.push(result);
    } catch (error) { errors.push({ path, message: error instanceof Error ? error.message : "기록을 읽지 못했습니다." }); }
  }
  return { documents, errors };
}
