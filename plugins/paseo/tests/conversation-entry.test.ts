import {test} from 'node:test';
import assert from 'node:assert/strict';
import {registerConversationEntries} from '../client/core.entry';

test('composer routes are exact and stale list results cannot undo live updates',async()=>{
 let receive:any,resolve:any;const registrations:any[]=[];const opened:any[]=[];let stopped=0;
 const client:any={paseo:{agents:{subscribe(fn:any){receive=fn;return()=>stopped++;},list(){return new Promise(r=>resolve=r);}}},
 addComposerPill(value:any){const row={...value,removed:false};registrations.push(row);return{remove(){row.removed=true;}};},
 openPanel(...args:any[]){opened.push(args);}};
 const dispose=registerConversationEntries(client);
 receive({kind:'upsert',agent:{id:'a',workspaceId:'new'}});
 resolve({entries:[{agent:{id:'a',workspaceId:'old'}},{agent:{id:'b',workspaceId:'other'}}],pageInfo:{hasMore:false}});
 await new Promise(r=>setImmediate(r));
 assert.equal(registrations.length,2);
 registrations[0].button.behavior.onPress();
 assert.deepEqual(opened,[['skip-current-agent',{workspaceId:'new',agentId:'a'}]]);
 receive({kind:'remove',agentId:'a'});assert.equal(registrations[0].removed,true);
 dispose();dispose();assert.equal(stopped,1);assert.ok(registrations.every(r=>r.removed));
 receive({kind:'upsert',agent:{id:'c',workspaceId:'w'}});assert.equal(registrations.length,2);
});
test('disposal before host listing resolves registers nothing',async()=>{
 let resolve:any;let count=0;
 const dispose=registerConversationEntries({paseo:{agents:{subscribe(){return()=>{};},list(){return new Promise(r=>resolve=r);}}},addComposerPill(){count++;}} as any);
 dispose();resolve({entries:[{agent:{id:'a',workspaceId:'w'}}],pageInfo:{hasMore:false}});
 await new Promise(r=>setImmediate(r));assert.equal(count,0);
});
