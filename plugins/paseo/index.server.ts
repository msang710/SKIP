import type {PluginServerContext} from "@getpaseo/plugin/server";
import {rpcResult} from "./shared/core.recovery";
import {coreSessions} from "./server/session-routing";
import {connectCore,queryCore,userCore,closeCore} from "./shared/core";
import {searchIntentInvocations} from "./shared/intent";
import {searchCoreInvocations} from "./server/core.invocations";
export default function contribute(server:PluginServerContext) {
 server.handle(connectCore,(input,{paseo})=>coreSessions.connect(paseo,input));
 server.handle(queryCore,(input,{paseo})=>rpcResult(()=>coreSessions.query(paseo,input.sessionId,input,input.query,input.payload)));
 server.handle(userCore,(input,{paseo})=>rpcResult(()=>coreSessions.user(paseo,input.sessionId,input,input.command,input.key,input.payload)));
 server.handle(closeCore,input=>coreSessions.close(input.sessionId,input));
 server.handle(searchIntentInvocations,({query})=>searchCoreInvocations(query));
 return ()=>coreSessions.dispose();
}
