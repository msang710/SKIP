import test from "node:test";
import assert from "node:assert/strict";
import { CoreSessions } from "./session-routing.server";
import type { Bridge } from "./core.bridge.server";

function fixture() {
  const calls: any[] = [], sent: any[] = [];
  const state = { status: "idle", thread: "thread-a", workspace: "workspace-a", provider: "codex", failSend: false, delivery: "pending" };
  const bridge: Bridge = { close() { calls.push({ operation: "closed" }); }, async call(p: any) {
    calls.push(p);
    if (p.operation === "card") return { ticket: "private-ticket" };
    if (p.operation === "user") return { data: { execution_id: "execution-a" } };
    if (p.operation === "query") return { data: { delivery: { state: state.delivery } } };
    if (p.operation === "claim") return { delivery_id: "delivery-a", execution_id: "execution-a", message_key: "message-a", payload: { work: "work-a" } };
    if (p.operation === "ack") state.delivery = p.outcome === "unknown" ? "delivery_unknown" : "accepted";
    return {};
  } };
  const api: any = {
    workspaces: { ref(id: string) { assert.equal(id, "workspace-a"); return { async refresh() { return { id, projectId: "logical-project", projectRootPath: "/repo" }; } }; } },
    agents: { ref(id: string) { assert.equal(id, "agent-a"); return {
      async refresh() { return { agent: { id, workspaceId: state.workspace, cwd: "/repo", provider: state.provider, runtimeInfo: { sessionId: state.thread }, status: state.status } }; },
      timeline: { subscribe() { return () => {}; } },
      async send(text: string, options: any) { sent.push({ id, text, options }); if (state.failSend) throw new Error("response lost"); },
    }; } },
  };
  const sessions = new CoreSessions(() => bridge, async () => "portable-project");
  const binding = { uiInstanceId: "ui-a", workspaceId: "workspace-a", agentId: "agent-a" };
  return { calls, sent, state, api, sessions, binding };
}

test("only the current verified agent receives a message", async () => {
  const f = fixture(), c = await f.sessions.connect(f.api, f.binding);
  await f.sessions.user(f.api, c.sessionId, f.binding, "execution.prepare", "click-a", { work_id: "work-a" });
  assert.equal(f.sent.length, 1); assert.equal(f.sent[0].id, "agent-a"); assert.equal(f.sent[0].options.messageId, "message-a");
  assert.equal(f.calls.filter(c => c.operation === "ack")[0].outcome, "accepted"); f.sessions.dispose();
});
test("a workspace view cannot silently select an agent", async () => {
  const f = fixture(), binding = { ...f.binding, agentId: undefined }, c = await f.sessions.connect(f.api, binding);
  assert.equal(c.canStart, false);
  await assert.rejects(f.sessions.user(f.api, c.sessionId, binding, "execution.prepare", "click-a", {}));
  assert.equal(f.sent.length, 0); f.sessions.dispose();
});
test("busy, wrong UI and changed provider session never dispatch", async () => {
  const f = fixture(), c = await f.sessions.connect(f.api, f.binding);
  f.state.status = "running";
  await assert.rejects(f.sessions.user(f.api, c.sessionId, f.binding, "execution.prepare", "a", {}));
  f.state.status = "idle";
  await assert.rejects(f.sessions.user(f.api, c.sessionId, { ...f.binding, uiInstanceId: "other" }, "execution.prepare", "b", {}));
  f.state.thread = "thread-b";
  await assert.rejects(f.sessions.user(f.api, c.sessionId, f.binding, "execution.prepare", "c", {}));
  assert.equal(f.sent.length, 0); assert.ok(f.calls.some(v => v.operation === "closed"));
});
test("an uncertain send is not replayed", async () => {
  const f = fixture(), c = await f.sessions.connect(f.api, f.binding); f.state.failSend = true;
  await assert.rejects(f.sessions.user(f.api, c.sessionId, f.binding, "execution.prepare", "a", {}));
  assert.equal(f.state.delivery, "delivery_unknown"); f.state.failSend = false;
  await f.sessions.user(f.api, c.sessionId, f.binding, "execution.prepare", "a", {});
  assert.equal(f.sent.length, 1); f.sessions.dispose();
});
test("selection is stored without calling the agent", async () => {
  const f = fixture(), c = await f.sessions.connect(f.api, f.binding);
  await f.sessions.user(f.api, c.sessionId, f.binding, "decision.select", "a", { decision_id: "d", revision: 1, option_id: "keep" });
  assert.equal(f.sent.length, 0);
  assert.ok(f.calls.some(v => v.operation === "user" && v.ticket === "private-ticket")); f.sessions.dispose();
});

import { TurnReceipt } from "./turn-receipt";
test("finish requires exact message and turn, and waits for accepted delivery", () => {
  const reports: string[] = [], tracker = new TurnReceipt("mine", (state, turn) => reports.push(state + turn));
  tracker.event({ type: "turn_completed", turnId: "unrelated" });
  tracker.event({ type: "timeline", turnId: "t", item: { type: "user_message", clientMessageId: "mine" } });
  tracker.event({ type: "turn_completed", turnId: "other" });
  assert.deepEqual(reports, []);
  tracker.event({ type: "turn_completed", turnId: "t" });
  assert.deepEqual(reports, []);
  tracker.acknowledge(); tracker.acknowledge();
  assert.deepEqual(reports, ["finishedt"]);
});

test("expiry can reconnect only the same panel and never replays a write", async () => {
  const f=fixture(), c=await f.sessions.connect(f.api,f.binding);
  const original=Date.now;
  try {
    Date.now=()=>original()+31*60_000;
    await assert.rejects(f.sessions.query(f.api,c.sessionId,f.binding,"status",{}),(e:any)=>e.code==="CONTEXT_EXPIRED");
    const next=await f.sessions.connect(f.api,f.binding);
    await f.sessions.query(f.api,next.sessionId,f.binding,"status",{});
    assert.equal(f.calls.filter(c=>c.operation==="user").length,0);
    assert.equal(f.sent.length,0);
    await assert.rejects(f.sessions.query(f.api,next.sessionId,{...f.binding,uiInstanceId:"another"},"status",{}));
  } finally { Date.now=original; f.sessions.dispose(); }
});
