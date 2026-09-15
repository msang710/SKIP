# SKIP Core generation 1

The Python application API owns all business state. SQLite is the sole runtime record store. The portable project/source identity is distinct from a host's actual paths and connection. Never read old MD/YAML records to infer new goals or permissions.

## Entry and query

Prefer connected MCP tools: `skip_status`, `skip_context`, `skip_decisions`, `skip_assess_risk`, `skip_submit`, `skip_amend`, `skip_result`, `skip_observe`, `skip_record_result`, `skip_execution_status`.

Installed Linux uses `skip --workspace <root>` and `skip diagnose` through the active launcher. Do not select an old resolved release path from conversation history. For source development, the module CLI is `python -m skip_core.cli --project <id> query <status|inbox|context|record|trace|execution.status|settings|risks> --input '<JSON>'`. `--workspace` supplies an explicitly connected source root. Commands come from stdin to `command`; this route is agent-only and cannot grant user authority. `activate`/`request` are actual interactive fallback entrypoints. Do not simulate their confirmation.

The Codex native module is `python -m adapters.codex.entry --workspace <root> [--project <id>] [--goal <id>]`. The adapter reads only the selected actual host session. On Windows the distributed `skip.cmd` uses the bundled interpreter. `--activate` accepts a current explicit SKIP invocation and creates project/source metadata only. Repeating an anchored request is idempotent. Host formats with no stable user-message identity fail closed.

`--begin-current '<JSON>'` takes work_id, revision, goal_risk_id and change_risk_id. It validates the current user turn and starts a Core execution for that already-running agent, without sending another prompt. `--finish-current <execution-id>` records that agent's work report; evidence completeness remains separate. UI dispatch uses the native adapter channel instead.

For writing records, use [authoring-tools.md](authoring-tools.md). The low-level revision API remains available for compatibility.

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

## Caller, retries, and source connection renewal

A verified caller, a transport connection, and execution authority are distinct.
Codex agent CLI retries use host-verified conversation/workspace identity in a
versioned, transport-specific receipt namespace. Native human receipts retain
existing semantics. Old receipts are preserved; no ambiguous old caller IDs are
reassigned. Different transports are not assumed to represent the same caller.
Unknown CLI clients configure a stable `--receipt-scope` per client. This is an
explicit retry namespace, never proof of human identity or permission. Without
verified provenance or an explicit namespace, CLI mutations return CALLER_UNVERIFIED
rather than silently losing deduplication. Reads remain available. MCP clients can
also configure --receipt-scope for reconnect-safe retries; otherwise unknown hosts
have connection-local receipts only. Host configuration owns this namespace, not
individual model command payloads.

Source-only MCP contexts revalidate the configured source and renew after expiry.
They cannot acquire or extend native execution authority. Execution status exposes
connection.state: current, revalidation_required, target_changed, or unverified.
The compatibility connection_current flag describes a connection, not an agent.
A different receipt connection never authorizes retransmission of an old execution.

For installed Linux use the active `skip --workspace <root>` launcher, not an old
runtime/releases path. `skip diagnose` reports Core version/root, DB path and schema
compatibility. Packaged Windows entrypoints use their bundled runtime. Development
module invocation remains a source checkout fallback. SQLite access, read-only,
busy/locked, corruption, and actual schema mismatch errors remain distinct; queries
never migrate or replace the DB in response to an error.

## Saved requests and incomplete decisions

`request.list` supports goal_id/cursor/limit and returns bounded previews; `request` takes id and returns exact text and linked goals within the current project. MCP exposes skip_requests/skip_request. UI save does not dispatch; an explicit request attachment targets only the current composer. Reading or attaching a request never grants execution authority.

Inbox action_state distinguishes needs_options, needs_selection and selected. Historical decisions without options remain readable under records needing clarification, not actionable decision cards. Preserve paging across both classes; do not invent missing options or approvals.

## Current decision reads

Decision `record`, `inbox`, and `context` projections share `selection`, `selected_option`, `selection_state` and `selection_stale`. A revoked, superseded or wrong-revision selection is never returned as the active choice. Context budgeting counts these fields and reports omitted records as incomplete. Context completeness is not approval or proof that every decision is resolved.

Codex entry with an explicit goal includes a freshly queried restore context, including on status/continuation turns. New requests include their resulting goal context; no goal is inferred from a latest unrelated selection. Current-turn execution returns `decision_basis` used at entry. These are reads and gate results, not automatic model injection or permission to skip the gate. Before a relevant answer or resumed implementation, the skill reads the current context through CLI or MCP. No host hook is required.

## Learning generation (schema 5)

`learning.propose` stores typed failure/guideline/claim/boundary/environment/obligation/scenario versions with exact links. `learning.accept` is native-human only and binds a product selection to the exact contract digest. `failure.report`, `failure.attempt.record`, `guideline.assess`, `verification.run.start/finish`, `assurance.evaluate` share the standard receipt envelope. `learning.list/record`, `guidance`, `assurance` are bounded read queries. MCP `skip_learning` and `skip_record_learning` are thin wrappers; acceptance is not exposed to agents.

Environment manifests must match their attached evidence payload. Run injection and behavior results differ. All required scenarios at the declared boundary must have matching evidence; empty contracts, wrong environments, unfinished runs and conflicting runs never become supported. Candidate contracts remain advisory; accepted contract changes invalidate preflight. Physical write interception is not included.

Use explicit `upgrade-candidate` to create and validate a new upgraded DB copy. It does not switch the active DB. Stop writers and verify no intervening writes before a separately authorized cutover; do not run old writers on schema 5 or roll back only the executable. Existing historical FAIL backfill is not automatic.

## Entry and stage contract (schema 6 development)

`input.ingest` is native-only and derives route and content from Principal, never model-supplied `verified` JSON. Native `request.submit` also records its input and initial parser interpretation atomically. `intent.propose` appends a CAS revision under that request with acts, constraints, exact targets, instruction spans and unresolved reasons. It cannot discard explicit prohibitions or promote its caller's authority.

`entry.inspect` and `stage.assess` are read-only; `context` accepts an explicit request_id and supplies entry_basis/stage_assessment within the same response budget. Stage assessment is a preparation projection, not execution approval. Existing execution basis still validates precise work/requirement/plan/check relationships and now includes current intent constraints and target freshness.

Schema 6 reuses interactions, requests and events. Immutable input_envelopes store bounded structured content parts as one JSON body; intent_interpretations, action_proposals and response_bindings retain exact revisions through project-scoped foreign keys. A proposal's display_ref binds a short reply only when the native adapter verifies the exact shown proposal; native UI additionally uses the existing exact-command ticket. Scope or target changes require a new proposal. Actual host connection handles remain ephemeral. These adapter assertions do not isolate arbitrary same-OS-user code.

Host-provided structured roles are authoritative only to the extent the adapter verifies them. Codex text envelope and selector classification remain explicitly parser-derived; unsupported mixed content is not silently promoted. Plain text cannot establish which original UI injected it. The initial suggestion parser is intentionally conservative and not a complete semantic classifier. Complex requests require a grounded interpretation and native authorization; no confidence score creates authority.

Upgrade only a new candidate DB first. Old inputs remain readable without reconstructed provenance. Do not run a schema-4/5 writer against schema 6 or rewrite project history to make old inputs appear verified.

## Project introduction (schema 7 development)
SQLite stores immutable introduction versions/reviews, project-scoped adapter participation and explicit full-response read receipts. `project.profile.propose` is agent-callable; save/accept/reject require native human authority. Expected accepted revision is nullable for first creation; CAS rejects concurrent overwrites. `query project.profile` explicitly reads an accepted revision; `include_proposals` is for review and does not record an agent read. Query may store participant/read bookkeeping without advancing the business changes sequence. Receipts mean full response construction, not delivery or comprehension. Status/context returns metadata and lookup path, never automatically injects the introduction body even on a new session. Unknown identities stay unknown. No previous session reads imply memory in a new session. UI reads never mark agent reads. Re-query is always permitted. Candidate-only upgrade retains existing history; do not run older writers against schema 7.

## Input authoring (schema 8 development)

Native input capture precedes any goal or request materialization. `entry.inspect` accepts exactly one input_id or request_id. `intent.propose` accepts an input_id plus input_digest before a request exists. `entry.submit` combines that interpretation with a create/existing/none target and an optional authoring bundle in one transaction. All inputs retain original text and verified origin; the submitting model remains an agent. A new request uses the `record` discriminator, never implementation authority. Request-based interpretation queries remain compatible.

Schema 8 adds input_intent_versions and immutable input_materializations, and extends requests.operation using a table rebuild. Explicit upgrade uses a transaction with FK validation before commit and restores FK enforcement on exit. No old record IDs, text, provenance or approvals are rewritten. Test a candidate copy first; no automatic live upgrade. Old writers reject the newer schema.

Parser suggestions are advisory. Unknown means unresolved; it is not answer, approval, or a reason to demand magic wording. A structured proposal can be checked for valid spans, targets and preserved constraints; these checks do not prove semantic understanding. Native execution authorization is independent and retains its own current-turn/exact-action checks.

## Goal lifecycle (schema 9 development)

Goals support active, held, completed and archived. Completed means explicitly marked finished, not inferred from a passing test or a finished execution. Archived is retained history, not completion proof. `record.lifecycle` remains native-human-only; document kinds have the separate states described below. `goal.list` / `skip_goals` returns all goal states with bounded pagination. Default status lists active and held goals; exact-goal status/context and record reads retain completed/archived access. The Paseo goal navigator groups completed and archived under 지난 목표, with 완료 and 보관 subgroups; held stays in the current list with a 보류 label. No old goal is automatically reclassified by migration.

## Native goal transitions

`goal.transition` is a native-human command over the exact currently verified input. `skip_update_goals` calls the Codex host adapter, which rereads the actual current turn; it does not promote the MCP agent Principal. `skip-codex --update-goals` exposes the same path without custom scripts. Native UI adapters use `goal.set_state` with their verified event/ticket and the displayed goal id, revision, state_version, from_state and to_state. It shares transition validation without requiring a chat input envelope. Undo submits the returned state_version and reverses the transition; concurrent changes reject it instead of overwriting newer state. Input IDs from a different turn, quoted instruction spans, changed content/state_version, cross-goal evidence and active executions reject the batch. The command stores reasons and supporting refs in its receipt and creates no execution authorization or check results. Semantic interpretation remains the agent's responsibility; valid spans alone do not prove that a goal should be completed.


## Document states and replacement links

Schema 10 adds `rejected` and `superseded` to decisions, requirements, plans and work items. Goal states remain active/held/completed/archived. Evidence is immutable observation data and has no document-state menu. The migration preserves existing rows and re-creates all affected indexes and triggers; no content is re-imported or reclassified.

Native UI `record.set_state` accepts kind/id/revision/state_version/from_state/to_state, plus a reason for rejection or replacement, and an exact same-kind replacement reference for supersession. The replacement must be a different, current active record in the same goal. Reasons remain free text. State changes do not rewrite references or change the goal, grant execution permission, or create passing evidence. Unresolved executions in the goal block document state changes. Stale content or lifecycle rejects the mutation. Undo is a new checked transition using the returned version and previous state, reason and replacement; it never deletes history or overwrites a later change.

All goal and document lifecycle writes share `record_state_changes`, an immutable event-linked history. `record` includes the latest `state_change` (reason and exact replacement). Read bounded history through `record.state_history` / `skip_record_state_history`. Native UI uses the same verified event/ticket channel as goal actions, without asking the agent to interpret a chat request.

Default record lists and current context exclude rejected, superseded and archived documents. Use `record.list` / `skip_records` with `include_inactive=true` to inspect them; the UI offers 지난 기록 포함. Context separately includes bounded `inactive_records` warnings with reasons and replacement references, with explicit expansion requirements if truncated. These warnings are not implementation instructions. Read the replacement before applying it, and revise the affected explicit references: execution rejects an inactive referenced design, requirement, decision or work dependency instead of silently substituting its replacement.

## Codex semantic execution binding

`--begin-current` consumes the latest saved interpretation of the exact current native input (or an already native-verified exact proposal reply). Parser action suggestions and the legacy continuation phrase list do not authorize execution. A missing interpretation returns `INTERPRETATION_REQUIRED` for agent-side submission through the existing entry tools. It does not require a new user approval.

Explicit actions must be bound to the selected goal or exact work. A `resume` action must name the exact work and inherit a permitted action from applicable prior verified inputs in the same conversation, including saved requests awaiting their first execution and exact proposal replies. Current constraints and the referenced authorization request remain applicable. A planning-only request by itself cannot become implementation through `resume`. The native adapter rechecks the semantic basis when Core enters its transaction. Changed input, selected record revision or interpretation requires refresh. Finish reports the existing execution in the same conversation and never starts another action.

Execution preparation preserves the work's authoring request and binds its authorization to the current verified user interaction. The execution request points to the original input; current semantics are resolved without copying them. Core checks execution-stage restrictions against this request; it does not inherit the authoring request's temporary planning-only restriction. Delivery revalidates the authorization's request so it cannot fall back to the obsolete planning restriction. Durable decisions, requirements, selections, source/risk snapshots and dependencies are checked independently and are not relaxed by a new execution request. No schema migration or work duplication is required.

## Shared request interpretation

`skip_core.request_intent` owns semantic resolution, CAS writing, selected-target/work matching and continuation authorization. Codex verifies native input provenance and delegates to this module. Core preparation and delivery revalidation use the same resolved receipt, including anchor input IDs, interpretation source/revision/digest and proposal scope when applicable.

Both input-ID and request-ID amendments append to `input_intent_versions` in the current schema. Existing `intent_interpretations` rows remain immutable history and are read by event sequence with the input history. Native exact proposal bindings participate in that ordering. Same-event conflicting semantic heads fail with CONFLICT; an explicit CAS amendment reconciles them. No schema upgrade or record migration is introduced.

Selected work items are a set, not an equality requirement against every item. Selected plans, requirements and decisions must be reachable through the executing work's exact relationships. Continuations search bounded earlier verified inputs in the same conversation. A matching newer stop/prohibition cannot be skipped in favor of an older approval; unrelated targets cannot supply authority. Recursive continuation receipts and proposal scopes remain part of execution-basis revalidation.
