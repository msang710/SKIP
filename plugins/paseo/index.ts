import type { PluginContext } from "@getpaseo/plugin";
import { intentInvocationSource, searchIntentInvocations } from "./intent.shared";
import { searchIntent } from "./intent.server";
import { IntentRecordsPanel } from "./records.client";
import { decisionInbox, exactRecordAttachment, listRecords, readRecord, resolveProject, searchRecordAttachments } from "./records.server";
import { getDecisionInbox, getIntentRecordAttachment, intentRecordSource, listIntentRecords, readIntentRecord, resolveIntentProject, searchIntentRecords } from "./records.shared";

export default function contribute(plugin: PluginContext) {
  plugin.handle(searchIntentInvocations, ({ query }) => searchIntent(query));
  plugin.handle(resolveIntentProject, ({ paseoProjectId, projectRootPath }) => resolveProject(paseoProjectId, projectRootPath));
  plugin.handle(listIntentRecords, async ({ paseoProjectId, projectRootPath, scope, query }) => {
    const project = await resolveProject(paseoProjectId, projectRootPath);
    return { projectId: project.projectId, items: await listRecords(project.projectId, scope, query) };
  });
  plugin.handle(readIntentRecord, ({ projectId, relativePath }) => readRecord(projectId, relativePath));
  plugin.handle(getIntentRecordAttachment, ({ projectId, relativePath }) => exactRecordAttachment(projectId, relativePath));
  plugin.handle(getDecisionInbox, async ({ paseoProjectId, projectRootPath, goal }) => {
    const project = await resolveProject(paseoProjectId, projectRootPath);
    return decisionInbox(project.projectId, goal);
  });
  plugin.handle(searchIntentRecords, ({ query }) => searchRecordAttachments(query));
  plugin.addAttachmentSource(intentInvocationSource);
  plugin.addAttachmentSource(intentRecordSource);
  plugin.addWorkspacePanel({
    id: "intent-records",
    title: "SKIP Records",
    icon: "FileText",
    context: "workspace",
    locations: ["workspace", "explorer"],
    Component: IntentRecordsPanel,
  });
  plugin.addCommandCenterItem({
    id: "open-intent-records",
    title: "Open SKIP Records",
    icon: "FileText",
    keywords: ["intent", "now", "spec", "기록"],
    context: "workspace",
    onSelect({ openPanel }) { openPanel("intent-records"); },
  });
  return () => {};
}
