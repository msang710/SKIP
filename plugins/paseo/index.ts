import type { PluginContext } from "@getpaseo/plugin";
import { CorePanel } from "./core.panel.client";
import { coreSessions } from "./session-routing.server";
import { connectCore, queryCore, userCore, closeCore } from "./core.shared";
import { intentInvocationSource, searchIntentInvocations } from "./intent.shared";
import { searchCoreInvocations } from "./core.invocations";

export default function contribute(plugin: PluginContext) {
  const cleanup: Array<() => void> = [];
  plugin.handle(connectCore, (input, { paseo }) => {
    if (!cleanup.length) cleanup.push(() => coreSessions.dispose());
    return coreSessions.connect(paseo, input);
  });
  plugin.handle(queryCore, (input, { paseo }) => coreSessions.query(paseo, input.sessionId, input, input.query, input.payload));
  plugin.handle(userCore, (input, { paseo }) => coreSessions.user(paseo, input.sessionId, input, input.command, input.key, input.payload));
  plugin.handle(closeCore, (input) => coreSessions.close(input.sessionId, input));
  plugin.handle(searchIntentInvocations, ({ query }) => searchCoreInvocations(query));
  plugin.addAttachmentSource(intentInvocationSource);
  plugin.addWorkspacePanel({ id: "intent-records", title: "SKIP", icon: "ListFilter", context: "workspace", locations: ["workspace", "explorer"], Component: CorePanel });
  plugin.addWorkspacePanel({ id: "skip-current-agent", title: "SKIP", icon: "ListFilter", context: "agent", Component: CorePanel });
  plugin.addCommandCenterItem({ id: "open-skip-workspace", title: "SKIP 현재 상태", icon: "ListFilter", context: "workspace", onSelect({ openPanel }) { openPanel("intent-records"); } });
  plugin.addCommandCenterItem({ id: "open-skip-agent", title: "SKIP 이 대화에서 작업", icon: "ListFilter", context: "agent", onSelect({ openPanel }) { openPanel("skip-current-agent"); } });
  return () => { for (const stop of cleanup) stop(); };
}
