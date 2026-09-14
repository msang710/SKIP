import { defineRpc } from "@getpaseo/plugin";
import { z } from "zod";
const id = z.string().min(1).max(200);
const bound = { sessionId: id, uiInstanceId: id, workspaceId: id, agentId: id.optional() };
const result = z.record(z.string(), z.unknown());
export const connectCore = defineRpc({ name: "skip.core.connect", input: z.object({ uiInstanceId: id, workspaceId: id, agentId: id.optional() }), output: z.object({ sessionId: id, projectId: id, target: z.string(), canStart: z.boolean() }) });
export const queryCore = defineRpc({ name: "skip.core.query", input: z.object({ ...bound, query: z.enum(["goal.list", "project.profile", "changes", "entry.inspect", "stage.assess", "failure.history", "learning.list", "learning.record", "guidance", "assurance", "request.list", "request", "status", "inbox", "context", "record", "trace", "execution.status", "settings", "risks", "record.state_history", "record.list"]), payload: result }), output: result });
export const userCore = defineRpc({ name: "skip.core.user", input: z.object({ ...bound, command: z.enum(["record.set_state", "goal.set_state", "goal.transition", "project.profile.save", "project.profile.accept", "project.profile.reject", "learning.accept", "assurance.exception", "project.activate", "request.submit", "decision.select", "execution.prepare", "execution.cancel", "settings.update"]), key: id, payload: result }), output: result });
export const closeCore = defineRpc({ name: "skip.core.close", input: z.object(bound), output: z.object({ closed: z.boolean() }) });
