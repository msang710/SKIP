import test from "node:test";
import assert from "node:assert/strict";
import { rpcResult, message, reconnectable } from "./core.recovery";
test("expired connection is structured data, not a handler failure", async () => {
  const result = await rpcResult(async () => { throw Object.assign(new Error("private handler details"), {code:"CONTEXT_EXPIRED"}); });
  assert.equal(result.status,"error"); assert.equal(result.code,"CONTEXT_EXPIRED");
  assert.equal(reconnectable(result.code),true); assert.ok(!result.error.includes("private"));
});
test("conflict is not a connection retry and unknown errors do not leak RPC details", async () => {
  assert.equal(reconnectable("STALE"),false);
  const result = await rpcResult(async () => {throw Error("requestType=plugin.rpc.invoke.request code=handler_error");});
  assert.equal(result.code,"UNAVAILABLE"); assert.ok(!result.error.includes("requestType"));
  assert.ok(message("STALE").includes("최신"));
});
