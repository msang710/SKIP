import assert from "node:assert/strict";
import test from "node:test";
import { searchIntent } from "./intent.server";

function attachedInvocation(text: string | undefined): string | undefined {
  return text?.split("\n")[2];
}

test("returns bounded presets for an empty query", () => {
  const { items } = searchIntent("");
  assert.equal(items.length, 6);
  assert.deepEqual(
    items.map(({ identifier }) => identifier),
    ["현재", "재검증", "결정", "날짜", "비교", "도움말"],
  );
  assert.equal(attachedInvocation(items[0]?.text), "$skip --now");
});

test("builds a NOW goal invocation", () => {
  const { items } = searchIntent("now goal:runtime-secret-hardening verify");
  assert.equal(
    attachedInvocation(items[0]?.text),
    "$skip --now --goal runtime-secret-hardening --verify",
  );
  assert.equal(items[0]?.identifier, "사용자 지정");
});

test("normalizes historical date and artifacts", () => {
  const { items } = searchIntent("date:260825 artifacts:prd,user_stories decision:D-003");
  assert.equal(
    attachedInvocation(items[0]?.text),
    "$skip --date 2026-08-25 --artifacts prd,user-stories --decision D-003",
  );
});

test("builds an explicit compare invocation", () => {
  const { items } = searchIntent("now compare 260825 goal:runtime-secret-hardening");
  assert.equal(
    attachedInvocation(items[0]?.text),
    "$skip --now --compare --date 2026-08-25 --goal runtime-secret-hardening",
  );
});

test("rejects NOW and date without compare", () => {
  const { items } = searchIntent("now date:260825");
  assert.equal(items[0]?.resourceType, "SKIP validation error");
  assert.match(items[0]?.subtitle ?? "", /compare가 필요합니다/);
});

test("rejects invalid calendar dates", () => {
  const { items } = searchIntent("date:260231");
  assert.match(items[0]?.subtitle ?? "", /존재하지 않는 날짜/);
});

test("filters Korean presets with plain search words", () => {
  const { items } = searchIntent("제품 결정");
  assert.equal(items.length, 1);
  assert.equal(items[0]?.id, "now-decisions");
});

test("keeps English preset search aliases", () => {
  const { items } = searchIntent("product decisions");
  assert.equal(items.length, 1);
  assert.equal(items[0]?.id, "now-decisions");
});

test("returns side-effect-free help for help syntax", () => {
  for (const query of ["help", "--help", "--help --unknown now date:260231"]) {
    const { items } = searchIntent(query);
    assert.equal(items.length, 1);
    assert.equal(items[0]?.id, "help");
    assert.equal(items[0]?.identifier, "도움말");
    assert.equal(attachedInvocation(items[0]?.text), "$skip --help");
  }
});

test("finds help with the Korean display label", () => {
  const { items } = searchIntent("도움말");
  assert.equal(items.length, 1);
  assert.equal(items[0]?.id, "help");
});
