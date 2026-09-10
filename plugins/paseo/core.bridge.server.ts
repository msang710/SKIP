import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { randomBytes, randomUUID } from "node:crypto";
import path from "node:path";
import os from "node:os";
import { existsSync } from "node:fs";

export function coreRoot() {
  if (process.env.SKIP_CORE_ROOT) return process.env.SKIP_CORE_ROOT;
  if (typeof __dirname !== "undefined") {
    const source = path.resolve(__dirname, "../..");
    if (existsSync(path.join(source, "skip_core", "bridge.py"))) return source;
  }
  const base = process.platform === "win32" ? (process.env.LOCALAPPDATA ?? path.join(os.homedir(), "AppData", "Local")) : process.platform === "darwin" ? path.join(os.homedir(), "Library", "Application Support") : (process.env.XDG_DATA_HOME ?? path.join(os.homedir(), ".local", "share"));
  const data = process.env.SKIP_DATA_ROOT ?? path.join(base, "SKIP");
  return path.join(data, "runtime", "current");
}

export type Bridge = { call(payload: Record<string, unknown>): Promise<any>; close(): void };

/** Private parent channel. Never return its secret or process environment to UI/model tools. */
export class CoreClient implements Bridge {
  private child: ChildProcessWithoutNullStreams;
  private secret = randomBytes(32).toString("hex");
  private pending = new Map<string, { resolve(v: any): void; reject(e: Error): void; timer: ReturnType<typeof setTimeout> }>();
  private output = "";
  private closed = false;
  constructor(root = coreRoot()) {
    this.child = spawn(process.env.SKIP_PYTHON ?? "python3", ["-u", "-m", "skip_core.bridge"], {
      cwd: root, stdio: ["pipe", "pipe", "pipe"],
      env: { ...process.env, PYTHONPATH: root, SKIP_NATIVE_CHANNEL_SECRET: this.secret },
    });
    this.child.stdout.setEncoding("utf8");
    this.child.stdout.on("data", (chunk: string) => {
      this.output += chunk;
      if (this.output.length > 2_000_000) { this.fail(new Error("Core response exceeds limit")); return; }
      let end: number;
      while ((end = this.output.indexOf("\n")) >= 0) {
        const line = this.output.slice(0, end); this.output = this.output.slice(end + 1);
        try {
          const frame = JSON.parse(line), request = this.pending.get(frame.id);
          if (!request) continue;
          clearTimeout(request.timer); this.pending.delete(frame.id);
          if (frame.error) request.reject(Object.assign(new Error(frame.error.error), { code: frame.error.code }));
          else request.resolve(frame.result);
        } catch { this.fail(new Error("Invalid Core protocol response")); }
      }
    });
    this.child.stderr.on("data", () => {}); // Consume; avoid leaking host inputs into logs.
    this.child.on("error", (e) => this.fail(e));
    this.child.on("close", () => this.fail(Object.assign(new Error("Core connection closed"), {code:"CONNECTION_LOST"})));
    this.child.stdin.on("error", (e) => this.fail(e));
  }
  call(payload: Record<string, unknown>): Promise<any> {
    if (this.closed) return Promise.reject(Object.assign(new Error("Core connection closed"), {code:"CONNECTION_LOST"}));
    if (this.pending.size >= 32) return Promise.reject(new Error("Too many Core requests"));
    const id = randomUUID();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => this.fail(Object.assign(new Error("Core response timeout; outcome may be unknown"), {code:"OUTCOME_UNKNOWN"})), 30_000);
      this.pending.set(id, { resolve, reject, timer });
      this.child.stdin.write(JSON.stringify({ id, secret: this.secret, payload }) + "\n");
    });
  }
  private fail(error: Error) {
    if (this.closed) return;
    this.closed = true;
    for (const p of this.pending.values()) { clearTimeout(p.timer); p.reject(error); }
    this.pending.clear(); this.child.kill();
  }
  close() { this.fail(new Error("Current panel disconnected")); }
}
