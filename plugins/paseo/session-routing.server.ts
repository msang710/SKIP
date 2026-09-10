import { randomUUID } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import type { PaseoClient } from "@getpaseo/client";
import { CoreClient, coreRoot, type Bridge } from "./core.bridge.server";
type PaseoApi = Pick<PaseoClient, "workspaces" | "agents">;
import { TurnReceipt } from "./turn-receipt";
const exec = promisify(execFile);
export type Binding = { uiInstanceId: string; workspaceId: string; agentId?: string };
type Session = { binding: Binding; identity: string[]; projectId: string; bridge: Bridge; expires: number; canStart: boolean; target: string; busy: boolean; cleanup: Set<() => void> };

async function sourceIdentity(directory: string, project: string): Promise<string> {
  const root = coreRoot();
  const { stdout } = await exec(process.env.SKIP_PYTHON ?? "python3", ["-m", "adapters.common.identity", "--workspace", directory, "--fallback", project],
    { cwd: root, env: { ...process.env, PYTHONPATH: root }, timeout: 5000, maxBuffer: 8192 });
  const result = JSON.parse(stdout);
  if (typeof result.project_id !== "string") throw new Error("프로젝트 식별 결과가 올바르지 않습니다.");
  return result.project_id;
}

/** Per-plugin-process memory only. No API creates or searches for another agent. */
export class CoreSessions {
  private sessions = new Map<string, Session>();
  constructor(private makeBridge: () => Bridge = () => new CoreClient(), private identify = sourceIdentity) {}
  private async observe(api: PaseoApi, binding: Binding) {
    const ws = await api.workspaces.ref(binding.workspaceId).refresh();
    if (!ws) throw new Error("현재 작업 공간을 확인할 수 없습니다.");
    const directory = ws.workspaceDirectory ?? ws.projectRootPath;
    let provider = "", thread = "", status = "", title = "현재 대화 연결 필요";
    if (binding.agentId) {
      const ref = api.agents.ref(binding.agentId), value = await ref.refresh();
      if (!value || value.agent.workspaceId !== ws.id || value.agent.cwd !== directory) throw new Error("현재 대화와 작업 공간이 일치하지 않습니다.");
      provider = value.agent.provider;
      thread = value.agent.runtimeInfo?.sessionId ?? "";
      status = value.agent.status;
      title = value.agent.title ?? `${provider} 현재 대화`;
    }
    const projectId = await this.identify(directory, ws.projectId);
    return { identity: ["paseo", binding.workspaceId, directory, provider, binding.agentId ?? "", thread, binding.uiInstanceId],
      projectId, directory, title, status, canStart: Boolean(binding.agentId && thread) };
  }
  async connect(api: PaseoApi, binding: Binding) {
    for (const [id, session] of this.sessions) if (session.expires < Date.now() || session.binding.uiInstanceId === binding.uiInstanceId) { for (const stop of session.cleanup) stop(); session.bridge.close(); this.sessions.delete(id); }
    if (this.sessions.size >= 64) throw new Error("열린 SKIP 연결이 너무 많습니다.");
    const observed = await this.observe(api, binding), bridge = this.makeBridge();
    try {
      await bridge.call({ operation: "connect", project_id: observed.projectId, sources: { main: observed.directory }, identity: observed.identity, can_start: observed.canStart });
    } catch (e) { bridge.close(); throw e; }
    const sessionId = randomUUID();
    this.sessions.set(sessionId, { binding, identity: observed.identity, projectId: observed.projectId, bridge, expires: Date.now() + 30 * 60_000, canStart: observed.canStart, target: observed.title, busy: false, cleanup: new Set() });
    return { sessionId, projectId: observed.projectId, target: observed.title, canStart: observed.canStart };
  }
  private get(id: string, binding: Binding) {
    const s = this.sessions.get(id);
    if (!s || s.expires < Date.now() || s.binding.workspaceId !== binding.workspaceId || s.binding.agentId !== binding.agentId || s.binding.uiInstanceId !== binding.uiInstanceId) throw new Error("현재 화면의 연결이 만료됐습니다. 다시 연결하세요.");
    return s;
  }
  private async verify(api: PaseoApi, id: string, binding: Binding, start = false) {
    const s = this.get(id, binding), observed = await this.observe(api, binding);
    this.get(id, binding); // Recheck after await: the UI might have closed.
    if (JSON.stringify(s.identity) !== JSON.stringify(observed.identity) || s.projectId !== observed.projectId) {
      for (const stop of s.cleanup) stop(); s.bridge.close(); this.sessions.delete(id); throw new Error("작업 환경이 바뀌었습니다. 현재 화면에서 다시 연결하세요.");
    }
    if (start && (!s.canStart || observed.status !== "idle")) throw new Error("현재 대화가 실행 중이거나 확인되지 않았습니다. 선택을 저장하고 나중에 실행하세요.");
    return s;
  }
  async query(api: PaseoApi, id: string, binding: Binding, query: string, payload: Record<string, unknown>) {
    const s = await this.verify(api, id, binding);
    return s.bridge.call({ operation: "query", query, payload });
  }
  async user(api: PaseoApi, id: string, binding: Binding, operation: string, key: string, payload: Record<string, unknown>) {
    const starting = operation === "execution.prepare";
    const s = await this.verify(api, id, binding, starting);
    if (s.busy) throw new Error("이 화면의 이전 요청을 처리 중입니다.");
    s.busy = true;
    try {
      const command = { schema: "skip-core/v1", project_id: s.projectId, command: operation, key, payload };
      const ticket = operation === "project.activate" || operation === "request.submit" ? undefined : (await s.bridge.call({ operation: "card", command })).ticket;
      await this.verify(api, id, binding, starting);
      const text = operation === "request.submit" ? String(payload.text) : JSON.stringify({ action: operation, payload });
      const result = await s.bridge.call({ operation: "user", command, ticket, user_event: { id: key, text } });
      if (!starting) return result;
      // A replay reads the same execution; an accepted/unknown delivery must not be resent.
      const executionId = result.data.execution_id;
      const state = await s.bridge.call({ operation: "query", query: "execution.status", payload: { execution_id: executionId } });
      if (state.data.delivery.state !== "pending") return state;
      await this.verify(api, id, binding, true);
      const claim = await s.bridge.call({ operation: "claim", execution_id: executionId });
      try {
        await this.verify(api, id, binding, true);
        const agent = api.agents.ref(binding.agentId!);
        const tracker = new TurnReceipt(claim.message_key, (state, turn) => {
          void this.verify(api, id, binding).then(() => s.bridge.call({ operation: "finish", execution_id: executionId,
            state, receipt: { message_key: claim.message_key, turn_id: turn } })).catch(() => {}).finally(() => { stop(); s.cleanup.delete(stop); });
        });
        const stop = agent.timeline.subscribe(({ event }) => tracker.event(event));
        s.cleanup.add(stop);
        await agent.send("SKIP 실행 요청\n" + JSON.stringify(claim.payload), { messageId: claim.message_key });
        await s.bridge.call({ operation: "ack", delivery_id: claim.delivery_id, outcome: "accepted", receipt: { message_key: claim.message_key } });
        tracker.acknowledge();
      } catch (e) {
        // Never use another provider or retry an uncertain send.
        await s.bridge.call({ operation: "ack", delivery_id: claim.delivery_id, outcome: "unknown" }).catch(() => {});
        throw e;
      }
      return s.bridge.call({ operation: "query", query: "execution.status", payload: { execution_id: executionId } });
    } finally { s.busy = false; }
  }
  close(id: string, binding: Binding) { const s = this.get(id, binding); for (const stop of s.cleanup) stop(); s.bridge.close(); this.sessions.delete(id); return { closed: true }; }
  dispose() { for (const s of this.sessions.values()) { for (const stop of s.cleanup) stop(); s.bridge.close(); } this.sessions.clear(); }
}

export const coreSessions = new CoreSessions();
