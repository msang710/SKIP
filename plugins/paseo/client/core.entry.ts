import type {PluginClientContext, PluginButtonRegistration} from "@getpaseo/plugin/client";

/** Each composer owns its exact host/workspace/agent route. Never infer focus from activity. */
export function registerConversationEntries(client: PluginClientContext) {
  if (typeof client.addComposerPill !== "function") return () => {};
  let disposed = false;
  const buttons = new Map<string, {workspaceId:string; registration:PluginButtonRegistration}>();
  const changed = new Set<string>();
  function remove(id:string) { buttons.get(id)?.registration.remove(); buttons.delete(id); }
  function upsert(agent:{id:string;workspaceId?:string;archivedAt?:string|null}) {
    if(disposed) return;
    const {id,workspaceId} = agent;
    if(!workspaceId || agent.archivedAt) {remove(id);return;}
    if(buttons.get(id)?.workspaceId===workspaceId) return;
    remove(id);
    const registration=client.addComposerPill({id:`skip-${id}`,workspaceId,agentId:id,button:{
      title:"SKIP 기록",label:"SKIP",icon:"ListFilter",
      behavior:{kind:"action",onPress(){client.openPanel("skip-current-agent",{workspaceId,agentId:id});}},
    }});
    buttons.set(id,{workspaceId,registration});
  }
  const stop=client.paseo.agents.subscribe(update=>{
    if(disposed) return;
    if(update.kind==="upsert") {changed.add(update.agent.id);upsert(update.agent);}
    else if(update.kind==="remove") {changed.add(update.agentId);remove(update.agentId);}
  });
  async function load() {
    let cursor:string|undefined;
    do {
      const result=await client.paseo.agents.list({filter:{includeArchived:false},page:{limit:100,cursor}});
      if(disposed) return;
      for(const {agent} of result.entries) if(!changed.has(agent.id)) upsert(agent);
      cursor=result.pageInfo.hasMore ? result.pageInfo.nextCursor??undefined : undefined;
    } while(cursor);
  }
  // Command Center remains available if the initial host read fails; later updates add pills.
  void load().catch(()=>{});
  return ()=>{if(disposed)return;disposed=true;stop();for(const id of buttons.keys())remove(id);};
}
