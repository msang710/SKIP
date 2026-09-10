import { test } from "node:test";
import assert from "node:assert/strict";
import { decisionSummary, overview, nowOverview } from "./core.overview";
test("new users need no imported text for native goals, work and evidence", () => {
  assert.equal(overview({work_items:[],checks:[],remaining:[]},[],[]).empty,true);
  const goal={id:"g",lifecycle:"active",fields:{title:"새 목표"}};
  const work={id:"w",lifecycle:"active",fields:{title:"새 작업"},children:{checks:[{required:1}]}};
  const value=overview({work_items:[work],remaining:[{work_id:"w",state:"NOT_RUN"}],checks:[{id:"e",result:"FAIL"}]},[],[goal]);
  assert.equal(value.empty,false);
  assert.equal(value.goals[0].fields.title,"새 목표");
  assert.equal(value.work[0].displayState,"검증이 남아 있음");
  assert.equal(value.checks[0].result,"FAIL");
});
test("missing checks and historical results cannot imply fresh success", () => {
  const value=overview({work_items:[{id:"w",lifecycle:"active",fields:{},children:{checks:[]}}],remaining:[],checks:[{id:"old",result:"PASS",origin:{}}]},[],[]);
  assert.equal(value.work[0].displayState,"검증 조건 확인 필요");
  assert.equal(value.checks.length,0);
});
test("incomplete imported decisions do not pretend to be selectable cards", () => {
  const missing={id:"old",fields:{question:"old decision"},children:{options:[]},action_state:"needs_options"};
  const ready={id:"new",fields:{question:"choose"},children:{options:[{option_id:"a"},{option_id:"b"}]},action_state:"needs_selection"};
  const result=overview({work_items:[],checks:[],remaining:[]},[missing,ready],[]);
  assert.deepEqual(result.decisions.map(d=>d.id),["new"]);
  assert.deepEqual(result.incompleteDecisions.map(d=>d.id),["old"]);
});

test("NOW separates current facts from stale and imported facts without claiming completion", () => {
  const value=nowOverview({facts:[{id:'current',freshness:'current'},{id:'stale',freshness:'stale'},{id:'imported',freshness:'current',origin:{}}],
    work_items:[{id:'active',lifecycle:'active'},{id:'old',lifecycle:'active',origin:{}},{id:'held',lifecycle:'held'}],
    remaining:[{work_id:'active',state:'NOT_RUN'},{work_id:'old'},{work_id:'held'}],checks:[{id:'fail',result:'FAIL',freshness:'stale'},{id:'old',origin:{}}]});
  assert.deepEqual(value.facts.map((f:any)=>f.id),['current']);
  assert.deepEqual(value.previousFacts.map((f:any)=>f.id),['stale','imported']);
  assert.deepEqual(value.remaining,[{work_id:'active',state:'NOT_RUN'}]);
  assert.equal(value.checks[0].result,'FAIL');
  assert.equal(nowOverview({}).facts.length,0);
});

test("decision list distinguishes current choices from stale and revoked ones", () => {
  assert.equal(decisionSummary({selection_state:"unselected"}),"미결정");
  assert.equal(decisionSummary({selection_state:"selected",selected_option:{label:"현재 포커스 유지"}}),"결정됨 · 현재 포커스 유지");
  assert.match(decisionSummary({selection_state:"stale",selected_option:{label:"old"}}),/^재확인 필요/);
  assert.match(decisionSummary({selection_state:"revoked",selected_option:{label:"old"}}),/^미결정/);
});
