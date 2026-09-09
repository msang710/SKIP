import { defineAttachmentSource, defineRpc } from "@getpaseo/plugin/server";
import { z } from "zod";

export const intentItemSchema = z.object({
  id: z.string(),
  identifier: z.string(),
  title: z.string(),
  subtitle: z.string().optional(),
  url: z.string().url(),
  text: z.string(),
  resourceType: z.string(),
});

export const searchIntentInvocations = defineRpc({
  name: "intent-launcher.search",
  input: z.object({ query: z.string().max(500) }),
  output: z.object({ items: z.array(intentItemSchema).max(12) }),
});

export const intentInvocationSource = defineAttachmentSource({
  id: "intent-invocation",
  title: "SKIP",
  icon: "ListFilter",
  pickerTitle: "SKIP 호출 선택",
  searchPlaceholder: "예: help · now verify · date:260825 · goal:feature-name",
  search: searchIntentInvocations,
});
