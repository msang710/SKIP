import { defineRpc } from "@getpaseo/plugin/server";
import { z } from "zod";
const workspace = z.object({ workspaceId: z.string().min(1).max(200) });
const view = z.object({ schema: z.literal("status-view/v1"), goal: z.string().nullable(), outcome: z.string(),
  decision_needed: z.array(z.string()), recommendation: z.string().nullable(), risk_summary: z.array(z.string()),
  checks: z.array(z.unknown()), gaps: z.array(z.string()), next_action: z.string(), detail_refs: z.array(z.string()) });
const plan = z.object({ schema: z.literal("workflow-plan/v2"), status: z.string(), next_action: z.string(), view }).passthrough();
const job = z.object({ jobId: z.string(), plan });
export const inspectWorkflow = defineRpc({ name: "skip.workflow.inspect", input: workspace, output: plan });
export const activateWorkflow = defineRpc({ name: "skip.workflow.activate", input: workspace,
  output: z.object({ status: z.literal("applied"), project_id: z.string() }).passthrough() });
export const startWorkflow = defineRpc({ name: "skip.workflow.start", input: workspace.extend({ text: z.string().min(1).max(8192),
  operation: z.enum(["plan", "implement"]) }), output: job });
export const prepareWorkflow = defineRpc({ name: "skip.workflow.prepare", input: workspace.extend({ jobId: z.string().uuid(),
  assessment: z.record(z.string(), z.unknown()), receipt: z.record(z.string(), z.unknown()).optional() }), output: job });
export const workflowStatus = defineRpc({ name: "skip.workflow.status", input: workspace.extend({ jobId: z.string().uuid() }), output: job });
export const cancelWorkflow = defineRpc({ name: "skip.workflow.cancel", input: workspace.extend({ jobId: z.string().uuid() }),
  output: z.object({ status: z.literal("cancelled") }) });

export const reportWorkflow = defineRpc({ name: "skip.workflow.report", input: workspace.extend({ jobId: z.string().uuid(),
  result: z.record(z.string(), z.unknown()), source: z.record(z.string(), z.unknown()), writeNow: z.boolean().default(false),
  expectedRevision: z.string().optional(), sourceId: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/).optional() }), output: job });
