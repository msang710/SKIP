import { test } from "node:test";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import { WorkflowSessions } from "./workflow.server";
const workspace = { id: "w1", projectId: "p1", directory: "/native/workspace" };

test("native job keeps original user request; agent assessment cannot replace authority", async () => {
  const calls: any[] = [];
  const sessions = new WorkflowSessions(async (value) => { calls.push(value); return { status: "prepared" }; });
  const job = await sessions.start(workspace, "change the label", "implement");
  await sessions.prepare(workspace, job.jobId, { scope: { paths: ["a.txt"], summary: "label" } });
  assert.equal(calls[1].user_event.text, "change the label");
  assert.equal(calls[1].request.request_id, job.jobId);
  await assert.rejects(sessions.prepare(workspace, job.jobId, { text: "delete all data" }), /original user event/);
  await assert.rejects(sessions.prepare({ ...workspace, directory: "/other" }, job.jobId, {}), /unavailable/);
  const guarded = new WorkflowSessions(async () => ({ status: "prepared", authorization: { status: "ALLOW" } }));
  const approved = await guarded.start(workspace, "label", "implement");
  await guarded.prepare(workspace, approved.jobId, { scope: { paths: ["a.txt"], summary: "label" } });
  await assert.rejects(guarded.prepare(workspace, approved.jobId, { scope: { paths: ["a.txt", "b.txt"], summary: "expanded" } }), /scope changed/);

});

test("cancel, expiry and process restart invalidate ephemeral jobs", async () => {
  let now = 0;
  const sessions = new WorkflowSessions(async () => ({ status: "prepared" }), () => now);
  const first = await sessions.start(workspace, "request", "plan");
  sessions.cancel(workspace, first.jobId);
  await assert.rejects(sessions.status(workspace, first.jobId), /unavailable/);
  const second = await sessions.start(workspace, "request", "implement");
  now = 31 * 60 * 1000;
  await assert.rejects(sessions.status(workspace, second.jobId), /unavailable/);
  await assert.rejects(new WorkflowSessions().status(workspace, second.jobId), /unavailable/);
});

test("status reevaluates the core and activation is a separate event", async () => {
  const calls: any[] = [];
  const sessions = new WorkflowSessions(async (value) => { calls.push(value); return { status: "prepared" }; });
  await sessions.activate(workspace);
  assert.equal(calls[0].user_event.operation, "activate");
  assert.equal(calls[0].request, undefined);
  const job = await sessions.start(workspace, "request", "implement");
  await sessions.status(workspace, job.jobId);
  assert.equal(calls.length, 3);
});

test("Paseo adapter executes shared Python Core in the actual remote workspace", async () => {
  const root = await mkdtemp(join(tmpdir(), "skip-native-"));
  const previous = { ...process.env };
  try {
    const directory = join(root, "한글 workspace");
    await mkdir(directory);
    await writeFile(join(directory, "app.txt"), "old");
    process.env.INTENT_TO_CODE_RECORD_ROOT = join(root, "records");
    process.env.INTENT_TO_CODE_WORKSPACE_REGISTRY = join(root, "registry.yaml");
    process.env.SKIP_RUNTIME_SCRIPT = resolve("../../scripts/intent_context.py");
    const native = { ...workspace, directory };
    const sessions = new WorkflowSessions();
    assert.equal((await sessions.inspect(native)).next_action, "activate");
    await sessions.activate(native);
    const job = await sessions.start(native, "change a label", "implement");
    assert.equal(job.plan.next_action, "inspect_source");
    const measured = await sessions.prepare(native, job.jobId, { scope: { paths: ["app.txt"], summary: "label" } });
    assert.equal(measured.plan.source_snapshot.files[0].path, "app.txt");
    assert.equal(measured.plan.goal.method, "current-user-request");
    assert.equal(measured.plan.authorization.status, "BLOCKED");
    const scope = { paths: ["app.txt"], summary: "label" };
    const goalRisk = { schema: "goal-risk/v1", revision: 1, affects: [], failure_impact: "cosmetic",
      reversibility: "easy", uncertainty: "low", evidence: ["app.txt"] };
    const changeRisk = { schema: "change-risk/v1", goal_revision: 1, source_digest: measured.plan.source_snapshot.digest,
      scope_digest: createHash("sha256").update(JSON.stringify(scope)).digest("hex"), policy_version: "failure-cost/1",
      affects: [], reversibility: "easy", uncertainty: "low", evidence: ["app.txt"], exclusions: {} };
    const allowed = await sessions.prepare(native, job.jobId, { goal_risk: goalRisk, change_risk: changeRisk });
    assert.equal(allowed.plan.authorization.status, "ALLOW");
    await writeFile(join(directory, "app.txt"), "new label");
    const after = await sessions.prepare(native, job.jobId, {});
    assert.equal(after.plan.next_action, "inspect_source");
    const reported = await sessions.report(native, job.jobId, {
      schema: "workflow-result/v1", outcome_status: "complete", changes: ["The current label is new label"],
      evidence: [{ surface: "source", status: "PASS", reference: "app.txt", summary: "current contents checked" }],
      gaps: [], next_decision: null,
    }, after.plan.source_snapshot, true);
    assert.equal(reported.plan.next_action, "done");
    assert.match(reported.plan.recorded.path, /NOW/);
    assert.equal((await sessions.status(native, job.jobId)).plan.result.outcome_status, "complete");
    await writeFile(join(directory, "app.txt"), "later edit");
    await assert.rejects(sessions.status(native, job.jobId), /source changed/);

  } finally {
    for (const name of Object.keys(process.env)) if (!(name in previous)) delete process.env[name];
    Object.assign(process.env, previous);
    await rm(root, { recursive: true, force: true });
  }
});
