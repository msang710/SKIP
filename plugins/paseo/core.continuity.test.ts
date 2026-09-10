import test from "node:test";
import assert from "node:assert/strict";
import {itemKey,reconcile,readWindow} from "./core.continuity";

test("refresh preserves unchanged objects, updates revisions and keeps authoritative order",()=>{
 const a={kind:"plan",id:"a",revision:1},b={kind:"plan",id:"b",revision:1};
 const next=reconcile([a,b],[{...b},{...a,revision:2},{kind:"work_item",id:"a",revision:1}]);
 assert.equal(next[0],b);assert.notEqual(next[1],a);assert.equal(next[1].revision,2);
 assert.notEqual(itemKey(next[1]),itemKey(next[2]));
 assert.deepEqual(reconcile(next,[{...b}]),[b]);
});
test("refresh keeps the loaded 230 row window rather than resetting to one page",async()=>{
 const rows=Array.from({length:245},(_,id)=>({id})),sizes:number[]=[];
 const result=await readWindow(async p=>{sizes.push(p.limit);const start=Number(p.cursor??0),end=Math.min(start+p.limit,rows.length);return {status:"ok",sequence:7,data:{items:rows.slice(start,end),next_cursor:end<rows.length?String(end):null}};},{},"items",230);
 assert.equal(result.items.length,230);assert.equal(result.cursor,"230");assert.deepEqual(sizes,[100,100,30]);
});
test("concurrent edits retry a stale page once without mixing versions",async()=>{
 let calls=0;
 const result=await readWindow(async p=>{calls++;if(calls===2)return {status:"error",code:"STALE"};return {status:"ok",sequence:calls<3?1:2,data:{items:[{id:calls}],next_cursor:p.cursor?null:"next"}};},{},"items",2);
 assert.equal(calls,4);assert.equal(result.sequence,2);assert.deepEqual(result.items,[{id:3},{id:4}]);
});
test("persistent cursor conflict is bounded",async()=>{
 let calls=0;
 await assert.rejects(readWindow(async()=>{calls++;return {status:"error",code:"STALE"};},{},"items",30));
 assert.equal(calls,2);
});
