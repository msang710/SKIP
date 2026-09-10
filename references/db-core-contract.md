# SKIP Core generation 1

The Python application API owns all business state. SQLite is the sole runtime record store. The portable project/source identity is distinct from a host's actual paths and connection. Never read old MD/YAML records to infer new goals or permissions.

## Entry and query

Prefer connected MCP tools: `skip_status`, `skip_context`, `skip_decisions`, `skip_assess_risk`, `skip_propose`, `skip_observe`, `skip_record_result`, `skip_execution_status`.

The module CLI is `python -m skip_core.cli --project <id> query <status|inbox|context|record|trace|execution.status|settings|risks> --input '<JSON>'`. `--workspace` supplies an explicitly connected source root. Commands come from stdin to `command`; this route is agent-only and cannot grant user authority. `activate`/`request` are actual interactive fallback entrypoints. Do not simulate their confirmation.

The Codex native module is `python -m adapters.codex.entry --workspace <root> [--project <id>] [--goal <id>]`. The adapter reads only the selected actual host session. On Windows the distributed `skip.cmd` uses the bundled interpreter. `--activate` accepts a current explicit SKIP invocation and creates project/source metadata only. Repeating an anchored request is idempotent. Host formats with no stable user-message identity fail closed.

`--begin-current '<JSON>'` takes work_id, revision, goal_risk_id and change_risk_id. It validates the current user turn and starts a Core execution for that already-running agent, without sending another prompt. `--finish-current <execution-id>` records that agent's work report; evidence completeness remains separate. UI dispatch uses the native adapter channel instead.

## Command contract

See `schemas/skip-core-v1.json` for the versioned envelope and typed record fields. It is generated from the Core registry by `python -m scripts.generate_core_schema`.

```json
{"schema":"skip-core/v1","command":"record.propose_revision","key":"unique-command-key","project_id":"project-id","payload":{"kind":"plan","expected_revision":0,"request_id":"actual-request-id","goal_id":"goal-id","fields":{"title":"Plan","design_body":"Technical design","scope_description":"Scope","alternatives_body":"Alternatives","rollback_body":"Recovery"},"children":{"items":[{"item_id":"step-1","title":"Implementation step","design_body":"Change","verification_body":"Check","position":0}]}}}
```

A `request.submit` references a verified user interaction. Proposal commands may create new decisions/requirements/plans/work under that request's goal, but cannot invent a new goal. Revisions require the exact expected head; child relationships include exact versions. `decision.select` stores an option without starting work. `execution.prepare` requires a current native context, risk/source/policy checks and human authority; its outbox sends only through that same context. `execution.begin_current` is limited to an adapter that verifies the currently executing user turn.

Goal fields: title, intent, success_definition. Decision: question, rationale, risk_summary plus options. Requirement: title, statement, rationale plus criteria and exact decisions/selections. Plan: title, design_body, scope_description, alternatives_body, rollback_body plus items and exact requirements/decisions/selections. Work: operation, title, instruction_body, completion_definition, workflow_depth, request_id plus checks and exact requirement/plan-item dependencies. See `skip_core/records.py` for the bounded child registry; submit no SQL/table names.

## Risk, authority and evidence

Risk has eight dimensions: business_rules, inventory, money, permissions, sensitive_data, persisted_data, external_state, boot_recovery. Supply each as `{impact: none|material|unknown, explanation: text}` for goal_factors/change_factors. A scope is a bounded list of `{source_id, relative_path, access: read|modify|create|delete}`. The adapter measures current source content; no machine path belongs in the DB payload.

Unknown risk requires investigation; material impact requires full work for implementation. Exact selection links and current referenced revisions must remain valid. Context budgets do not loosen these checks. User rule settings are versioned DB values and part of policy freshness; model-visible tools cannot edit them as human authority.

After implementation, `skip_observe` measures the current read scope (include goal_id when reporting for a goal); `skip_record_result` records its snapshot_id, execution_id, surface, result, summary, method, and exact checks/criteria. Optional payload is `{media_type, text}` and is stored as a DB BLOB. All model results remain agent_report. A fact may cite observed evidence; NOT_RUN is never current-state proof.

Repeated keys with identical command content return the original receipt. Changed content with the same key conflicts. STALE requires refreshing the changed basis; unknown delivery never automatically resends. Same-work and overlapping-source active execution checks include unresolved attempts.

## Installation and recovery

The data root is platform-local outside the product repository; `SKIP_DATA_ROOT` is an explicit host override. Default file is `skip.db`. Querying never initializes a missing DB. Credentials, active UI challenges, actual paths and routing handles remain in the adapter/OS secret facility.

The candidate package contains only DB-aware runtime entrypoints. Source-tree legacy scripts remain for historical regression coverage; they are not imported by Core or distributed as runtime facades. No mixed writer deployment is supported. Reconnect existing agent sessions when activating a new Core generation.

`Database.backup` uses SQLite's backup API and checks integrity. `restore` rehearses recovery into a new file; it does not overwrite or activate an existing DB. Future schema/checksum mismatch refuses writes. After new DB records exist, restore only a compatible DB-aware runtime or a reviewed recovery generation, never an old file-store fallback.

Gates are advisory. SQL constraints and native adapter assertions do not isolate against arbitrary same-OS-user code or physically intercept host file writes.

## Restored records

A one-time authorized repair restores documented goals, decision statements,
requirements, plans, tasks and observations into the same native aggregates.
`record.list` / `skip_records` and `record` / `skip_record` expose both restored
and newly authored records. Origins contain the original status, date, source
identifier and unresolved references; they contain no live routing or authority.
Completed, superseded and rejected source documents may be excluded when the
user requests it. Their bytes remain in inactive recovery provenance.

Historical statements can lack the rejected alternatives, acceptance criteria or
exact dependencies required for a new executable plan. The maintenance-only
origin allows preserving that incomplete content without inventing children.
Normal authoring still requires those children. Execution checks reject missing
criteria/links and unresolved references. Confirmed historical product decisions
are retained as decisions; they do not create new selections or authorizations.
Historical observations retain their reported results but their snapshots never
satisfy a current-source gate. New native observations stay separate.
