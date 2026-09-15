import type {PluginClientContext} from "@getpaseo/plugin/client";
import {registerConversationEntries} from "./client/core.entry";
import {CorePanel} from "./client/core.panel";
import {intentInvocationSource} from "./shared/intent";
export default function contribute(client:PluginClientContext) {
 client.addAttachmentSource(intentInvocationSource);
 client.addWorkspacePanel({id:"intent-records",title:"SKIP",icon:"ListFilter",context:"workspace",locations:["workspace","explorer"],Component:CorePanel});
 client.addWorkspacePanel({id:"skip-current-agent",title:"SKIP",icon:"ListFilter",context:"agent",Component:CorePanel});
 client.addCommandCenterItem({id:"open-skip-workspace",title:"SKIP 현재 상태",icon:"ListFilter",context:"workspace",onSelect({openPanel}){openPanel("intent-records");}});
 client.addCommandCenterItem({id:"open-skip-agent",title:"SKIP 이 대화에서 작업",icon:"ListFilter",context:"agent",onSelect({openPanel}){openPanel("skip-current-agent");}});
 return registerConversationEntries(client);
}
