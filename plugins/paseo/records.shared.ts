import { defineAttachmentSource, defineRpc } from "@getpaseo/plugin/server";
import { z } from "zod";

export const recordScopeSchema = z.enum(["now", "history"]);

export const recordSummarySchema = z.object({
  projectId: z.string(),
  scope: recordScopeSchema,
  goal: z.string().optional(),
  artifact: z.string(),
  relativePath: z.string(),
  title: z.string(),
  status: z.string().optional(),
  created: z.string().optional(),
  updated: z.string().optional(),
  sourceRevision: z.string().optional(),
  verifiedAt: z.string().optional(),
  byteLength: z.number().int().nonnegative(),
});

export const recordAttachmentItemSchema = z.object({
  id: z.string(),
  identifier: z.string(),
  title: z.string(),
  subtitle: z.string().optional(),
  url: z.string().url(),
  text: z.string(),
  resourceType: z.string(),
});

export const resolveIntentProject = defineRpc({
  name: "intent-records.resolve-project",
  input: z.object({
    paseoProjectId: z.string().min(1).max(200),
    projectRootPath: z.string().max(4096),
  }),
  output: z.object({ projectId: z.string(), displayName: z.string() }),
});

export const listIntentRecords = defineRpc({
  name: "intent-records.list",
  input: z.object({
    paseoProjectId: z.string().min(1).max(200),
    projectRootPath: z.string().max(4096),
    scope: recordScopeSchema,
    query: z.string().max(500).default(""),
  }),
  output: z.object({
    projectId: z.string(),
    items: z.array(recordSummarySchema).max(250),
  }),
});

export const readIntentRecord = defineRpc({
  name: "intent-records.read",
  input: z.object({
    projectId: z.string().min(1).max(200),
    relativePath: z.string().min(1).max(4096),
  }),
  output: z.object({ record: recordSummarySchema, text: z.string() }),
});

export const getIntentRecordAttachment = defineRpc({
  name: "intent-records.get-attachment",
  input: z.object({
    projectId: z.string().min(1).max(200),
    relativePath: z.string().min(1).max(4096),
  }),
  output: recordAttachmentItemSchema,
});

export const decisionInboxItemSchema = z.object({
  id: z.string(),
  kind: z.string(),
  action: z.string().optional(),
  status: z.string(),
  reasons: z.array(z.string()).default([]),
  summary: z.string().nullish(),
  evidence: z.string().optional(),
  digest: z.string().optional(),
  caller: z.string().optional(),
});

export const getDecisionInbox = defineRpc({
  name: "intent-records.decision-inbox",
  input: z.object({
    paseoProjectId: z.string().min(1).max(200),
    projectRootPath: z.string().max(4096),
    goal: z.string().min(1).max(200),
  }),
  output: z.object({
    schema: z.literal("decision-inbox/v1"),
    project_id: z.string(),
    goal: z.string(),
    lifecycle: z.string(),
    items: z.array(decisionInboxItemSchema),
  }),
});

export const searchIntentRecords = defineRpc({
  name: "intent-records.search",
  input: z.object({ query: z.string().max(500) }),
  output: z.object({
    items: z.array(recordAttachmentItemSchema).max(50),
  }),
});

export const intentRecordSource = defineAttachmentSource({
  id: "intent-record",
  title: "SKIP Records",
  icon: "FileText",
  pickerTitle: "SKIP 기록 첨부",
  searchPlaceholder: "예: NOW · project:quickhack-public-portfolio · tasks",
  search: searchIntentRecords,
});

export const readRecordGroup = defineRpc({
  name: "intent-records.read-group",
  input: z.object({ projectId: z.string().min(1).max(200), paths: z.array(z.string().min(1).max(4096)).min(1).max(24) }),
  output: z.object({ documents: z.array(z.object({ record: recordSummarySchema, text: z.string() })), errors: z.array(z.object({ path: z.string(), message: z.string() })) }),
});
