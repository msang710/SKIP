import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { homedir, hostname } from "node:os";
import { dirname, join } from "node:path";

export type NativeWorkspace = { id: string; projectId: string; directory: string };
export type CoreCall = (payload: Record<string, unknown>) => Promise<any>;

/** Internal control channel. Shell interpolation and client-provided execution paths are forbidden. */
export const callCore: CoreCall = (payload) => new Promise((resolve, reject) => {
  const script = process.env.SKIP_RUNTIME_SCRIPT ?? join(homedir(), ".agents", "skills", "skip", "scripts", "intent_context.py");
  const child = spawn(process.env.SKIP_PYTHON ?? "python3", ["-X", "utf8", "-B", join(dirname(script), "native_entry.py")],
    { stdio: ["pipe", "pipe", "pipe"], env: process.env });
  let output = "";
  let error = "";
  const timer = setTimeout(() => { child.kill(); reject(new Error("SKIP Core timed out")); }, 15000);
  child.stdout.on("data", (data) => {
    output += data.toString("utf8");
    if (Buffer.byteLength(output) > 2 * 1024 * 1024) { child.kill(); reject(new Error("SKIP Core response too large")); }
  });
  child.stderr.on("data", (data) => { if (error.length < 4096) error += data.toString("utf8"); });
  child.on("error", (cause) => { clearTimeout(timer); reject(cause); });
  child.on("close", (code) => {
    clearTimeout(timer);
    try {
      const result = JSON.parse(output);
      if (code !== 0 || result.status === "error") throw new Error(result.error ?? "SKIP Core unavailable");
      resolve(result);
    } catch (cause) { reject(new Error(`SKIP Core: ${cause instanceof Error ? cause.message : error}`)); }
  });
  child.stdin.on("error", () => {});
  child.stdin.end(JSON.stringify(payload));
});

type Job = { workspace: NativeWorkspace; event: { id: string; text: string; operation: string };
  session: string; expires: number; request: Record<string, unknown>; result: any; executionGate?: any; reported?: Record<string, unknown> };

/** Process-memory only. A restart/expired job requires the actual user request again. */
export class WorkflowSessions {
  private readonly jobs = new Map<string, Job>();
  private readonly execution = `${hostname()}:${randomUUID()}`;
  constructor(private readonly execute: CoreCall = callCore, private readonly now = Date.now) {}

  private payload(workspace: NativeWorkspace, session: string) {
    return { host: { host_id: "paseo", execution_id: this.execution, session_id: session, workspace: workspace.directory },
      paseo_project_id: workspace.projectId };
  }
  private prune() {
    for (const [id, job] of this.jobs) if (job.expires <= this.now()) this.jobs.delete(id);
  }
  private get(workspace: NativeWorkspace, id: string) {
    this.prune();
    const job = this.jobs.get(id);
    if (!job || JSON.stringify(job.workspace) !== JSON.stringify(workspace)) throw new Error("Current user request unavailable for this workspace");
    return job;
  }
  async inspect(workspace: NativeWorkspace) {
    return this.execute({ ...this.payload(workspace, "inspect"), command: "prepare" });
  }
  async activate(workspace: NativeWorkspace) {
    return this.execute({ ...this.payload(workspace, randomUUID()), command: "activate",
      user_event: { id: randomUUID(), text: "activate", operation: "activate" } });
  }
  async start(workspace: NativeWorkspace, text: string, operation: "plan" | "implement") {
    this.prune();
    if (!text.trim() || text.length > 8192) throw new Error("A current user request is required");
    if (this.jobs.size >= 128) throw new Error("Too many active SKIP requests");
    const id = randomUUID();
    const event = { id, text, operation };
    const request = { schema: "workflow-request/v2", request_id: id, text, operation,
      scope: { paths: [], summary: text }, open_decisions: [] };
    const session = randomUUID();
    const result = await this.execute({ ...this.payload(workspace, session), command: "prepare", user_event: event, request });
    if (result.status === "project_missing") throw new Error("Activate this workspace before starting a request");
    this.jobs.set(id, { workspace, event, session, request, result, expires: this.now() + 30 * 60 * 1000 });
    return { jobId: id, plan: result };
  }
  async prepare(workspace: NativeWorkspace, id: string, assessment: Record<string, unknown>, receipt?: Record<string, unknown>) {
    const job = this.get(workspace, id);
    const allowed = new Set(["scope", "open_decisions", "goal", "goal_risk", "change_risk", "force_full"]);
    if (Object.keys(assessment).some((key) => !allowed.has(key))) throw new Error("Assessment cannot replace the original user event");
    const request = { ...job.request, ...assessment };
    if (job.executionGate && assessment.scope !== undefined &&
        JSON.stringify(assessment.scope) !== JSON.stringify(job.request.scope)) {
      throw new Error("Execution scope changed; a new native request is required for the expanded scope");
    }
    const result = await this.execute({ ...this.payload(workspace, job.session), command: "prepare", user_event: job.event, request, receipt });
    // Re-check cancellation/expiration after async execution.
    this.get(workspace, id);
    job.request = request;
    job.result = result;
    if (result.authorization?.status === "ALLOW") job.executionGate = result.authorization;
    return { jobId: id, plan: result };
  }
  async report(workspace: NativeWorkspace, id: string, result: Record<string, unknown>, source: Record<string, unknown>, writeNow: boolean, expectedRevision?: string, sourceId?: string) {
    const job = this.get(workspace, id);
    if (!job.executionGate) throw new Error("No current request execution basis was established");
    const report = { ...result, requested_outcome: job.event.text, authorization: job.executionGate };
    const payload = { ...this.payload(workspace, job.session), command: "report", user_event: job.event,
      request: job.request, result: report, source_snapshot: source, write_now: writeNow, expected_revision: expectedRevision, source_id: sourceId };
    const updated = await this.execute(payload);
    this.get(workspace, id);
    if (updated.recorded && updated.goal?.goal) {
      job.request = { ...job.request, goal: updated.goal.goal };
      payload.request = job.request;
    }
    job.reported = { ...payload, write_now: false };
    job.result = updated;
    return { jobId: id, plan: updated };
  }
  async status(workspace: NativeWorkspace, id: string) {
    const job = this.get(workspace, id);
    if (!job.reported) return this.prepare(workspace, id, {});
    const result = await this.execute(job.reported);
    this.get(workspace, id);
    return { jobId: id, plan: result };
  }
  cancel(workspace: NativeWorkspace, id: string) { this.get(workspace, id); this.jobs.delete(id); return { status: "cancelled" }; }
}
