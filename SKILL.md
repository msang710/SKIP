---
name: skip
description: Supervise coding work through current evidence, explicit product decisions and a shared SQLite Core. Use for meaningful feature planning, business rules, implementation and restoring an existing SKIP goal. Keep the user's IDE and agent; adapt procedure to failure cost. Skip trivial self-contained edits unless explicitly invoked.
---

# SKIP

Read the decisions. Skip the implementation details.

Use the current user's language. Keep FACT (observed), PRODUCT (human policy) and DESIGN (technical choice) distinct. Use the existing agent and IDE. Do not ask users to operate a documentation workflow.

## First entry

- A copied `$skip --project <id> query record --input <JSON>` invocation selects the exact record kind/id/revision. Read it through Core `record` / `skip_record`; do not replace it with the latest goal or create a goal from this selector. Reading a selected record is not execution approval.
- With no request, show short help. Do not create a goal.
- Start from this actual user request. Never invent past goals from code, Git, conversation summaries or agent memory.
- To inspect a request saved in the UI, use `skip_requests` then `skip_request` with its exact ID (CLI: `query request.list` / `query request --input '{"id":"..."}'`). Do not substitute the latest chat message. Saved requests and composer attachments are context, not permission to execute or deploy. Never choose an unrelated latest request automatically.
- Before answering about a saved decision or resuming work on a known goal, read fresh `skip_context` (CLI `query context`) for that exact goal. Read `selection`, `selected_option`, and `selection_state`; do not infer the user's choice from conversation memory or option order. Expand an incomplete pack before relying on omitted decisions. This is a tool-read workflow, not a host hook. Do not guess a goal when the current task does not identify one.
- Prefer the host's connected SKIP MCP tools. `skip_status` reads current facts; `skip_context` reads one explicit goal and stage. An incomplete pack is not enough to infer missing decisions or approvals.
- In Codex with local session provenance, the bundled `adapters.codex.entry` reads the current actual user turn. `--activate` connects the project with no goals; a subsequent request captures its original input without creating a goal. Use the returned entry_basis with skip_enter to save only the requested goal/records. Use `--goal` to continue an existing goal. A generic continuation/status request does not invent a new goal.
- On Windows use the plugin's bundled Python and modules. Do not ask the target user to install Python, SQLite, npm or Git. Source/CLI installation is a fallback for environments that already use it.
- If the host cannot verify current user provenance, keep reading/proposing through MCP and surface the missing native input path. Do not substitute `approved=true`, copied chat text or an agent-run interactive shell.

## Work from one source of truth

All SKIP business records, explanations, decisions, requirements, designs, tasks, evidence, settings and current facts live in SQLite through the Core API. Do not create or read parallel Markdown/JSON/YAML business stores, legacy ledgers, NOW files, importers or exporters. A user-authorized one-time migration may preserve historical originals and typed text in SQLite. Read imported history through `history` / `history.record` (or `skip_history` / `skip_history_record`), never through the old source files. Imported status is historical, not fresh approval or verification. Existing originals are retained as an inactive backup. Product source code stays in its own repository.

Read [references/db-core-contract.md](references/db-core-contract.md) when creating records, selecting context, changing policy, or using execution authority. CLI, MCP and native UI share this contract. Never write SQL directly to bypass it.

## Choose only the needed depth

- Answer a question directly when no development work is requested.
- Investigate when evidence or failure cost is unknown.
- Use compact work for a reversible low-impact change; do not generate artificial PRD/design records.
- Material business rules, permissions, inventory, money, persisted data or recovery effects need explicit goal/change risk and proportionate design/checks.
- Record goal and change risk explicitly against the current source snapshot. Do not equate small code changes with low impact.
- Reuse valid product decisions. When the user corrects a fact, recheck current source and explain whether it changed the conclusion.

## Decisions and implementation

Ask only material PRODUCT questions. Show the question, options, recommendation, reason and consequence. The agent owns technical design within the user's policy and authorized scope.

Use typed record revisions and exact selection/requirement/plan/work relationships. Publishing or sealing a record fixes its content; it is not human approval. A changed option, revision, source or policy requires the Core to reassess the relevant authority.

Preserve plan-only requests. After an implementation instruction, proceed within its authorized scope without asking the same question repeatedly. For the current Codex turn, use the native `--begin-current` path with exact work/risk references before material execution. The Core validates the real host user turn; passing references is not itself permission. For UI-started work, use the execution's current Core state. Never interpret an attachment or a context pack as authorization.

Only a verified current host adapter may send a new turn. Plans are portable; live host/workspace/agent/thread handles remain ephemeral. Do not search installed IDEs/providers, pick a recent agent, start a replacement session, or replay an old pending delivery into another environment. Unknown delivery and cancellation stay unknown until verified receipts resolve them.

## Failure learning and assurance

Prefer `skip_result` for verification: a routine FAIL stays evidence, and an explicit significant incident adds failure/attempt details in the same call. The low-level `evidence.record` compatibility path still creates a failure occurrence for every FAIL. Use `failure.report` for observed tool/user incidents and `failure.attempt.record` for unsuccessful fixes or recovery, referencing exact evidence. An expected injected error is `purpose=injection`, not proof of a product defect. Never invent a root cause or elevate agent_report to host evidence.

Before investigation, design or resumed work, read the goal's context and expand `failure_guidance` and `assurance` through `skip_learning` / CLI queries. Supply the observed snapshot and work when known. Unknown scope or truncated results is not "no relevant failures." Record evidence-backed applicability; a retired guideline, an irrelevant guideline and a non-reproduced failure are different states.

Express each consequential claim as explicit conditions plus required verification boundaries. Link scenarios and observed environment evidence to obligations. VM evidence cannot stand in for physical hardware; mock evidence cannot stand in for real DB competition. A random run with no injected failures has not tested failure handling. Read Core assurance before reporting completion: preserve missing obligations, conflicting evidence, exceptions and stale conditions. Creating candidate guidance does not impose human policy. Native acceptance and execution checks remain separate. No hooks are required; ordinary tool-read behavior depends on the agent following this contract.

## Verify and report

Keep source, unit/integration tests, package, installation, runtime and visual/device evidence distinct. Evidence submitted by the model is `agent_report`; never upgrade it to a host observation. Execution finish is not proof that required checks passed.

Record results against exact source snapshots and work/criterion IDs. NOW is a Core query of current facts and their evidence, not a file to refresh. Preserve FAIL, NOT_RUN, incomplete context and stale evidence.

Report **결과 / 확인 / 남은 일** (or equivalents in the user's language) briefly, with relevant record/source links. Describe what is implemented, what was actually tested and what remains unverified. Implementation does not authorize installation, restart, remote upload or deployment; evaluate those actions against the user's current authorization and the concrete target.

## Installed command paths

The installed skill root contains `skip_core`, `skip_mcp` and `adapters`. Run modules from that root or set `PYTHONPATH` to it; preserve the actual project directory with `--workspace`. The installed `skip` CLI resolves portable project identities from SQLite and accepts an explicit `--project` when needed. For example, `skip --workspace <actual-workspace> query status`. Its `command` action accepts the same agent command JSON on stdin and never grants human authority. `skip-mcp` runs the installed official stdio server. Do not invoke retired `scripts/intent_context.py` or file-based runtime writers after deployment.

## Input provenance and stage outputs

Read `entry.inspect` / `skip_entry` for the exact request; provide `request_id` to context when known. `stage.assess` reports preparation and required outputs without authorizing execution. CLI, MCP and native inputs share Core history. `legacy_unknown` is not a new verified user instruction.

Use native entry first to capture this actual turn. It returns `entry_basis.input_id`, `input.digest`, instruction parts, and a parser **suggestion**. Unknown wording is `unresolved`, not a status-only answer. Interpret the user's meaning yourself; do not ask them to repeat an equivalent keyword phrase. Preserving original text does not forbid submitting a structured interpretation grounded in that text.

Prefer `skip_enter` (CLI `enter`) with that exact input ID/digest, `expected_revision: 0` on first interpretation, body, target and records. Use `create_goal` + create target for an explicitly requested new goal, `record` for requested records, `design` for a plan, `tasks` for actual work items. `records: []` creates just the goal. For existing work use an exact goal revision. A target of `none` saves interpretation without creating a goal. Only ask when the meaning or target is materially ambiguous; prior conversation can supply context but never replaces the actual input or grants new authority. A selected record stays in its existing goal. Reuse the returned `authoring_base` for further submissions.

Do not infer implementation or deployment approval from a successful entry receipt. Native execution checks still apply. An unsupported host may read/propose, but cannot fabricate verified input. If an input was already materialized, use its saved authoring_base; do not invent a new input or duplicate goal. Empty entry/help and status queries do not create business artifacts.

Separate instruction parts from selected records, quotes and host supplements. A record selector alone reads that exact revision; its kind and content never determine the requested action. Submit complex intent with `intent.propose` / `skip_interpret`: cite the original instruction spans, preserve prohibitions and selected targets, and keep uncertain meaning explicit. Parser suggestions are not complete natural-language understanding or human authority.

For record writing, prefer `skip_submit`, `skip_amend`, and `skip_result`; read [references/authoring-tools.md](references/authoring-tools.md) for bundle aliases, partial edits and CLI fallback. Reuse the explicit goal/request from context's authoring_base. One receipt contains the committed records; do not reread them just to confirm your own successful write. Refresh relevant context when resuming work or before execution because another session may have changed decisions.

A design request produces a plan. A detailed implementation plan/tasks request produces actual linked work_items with checks and dependencies; use the committed receipt to confirm their exact links and checks. Choose the necessary preparation for failure cost, rather than forcing every stage on every task.

For a short approval that needs binding to a proposal, use `action.propose` / `skip_propose_action` with exact target revision, source snapshot digest and constraints. Show the concrete action and scope together with the returned `display_ref`. Codex verifies that reference in the immediately preceding assistant message; a hidden or merely stored proposal is insufficient. Native UI uses its exact-command ticket. Bare approval with no unambiguous shown reference requires a concise clarification. A response binding is not an execution; the existing execution path rechecks its target and source digest. Do not ask again when an existing explicit implementation request already covers the work.

## Project purpose and participation
Entry/context includes `project_profile` metadata only. A new session does not require reading the introduction. Use `skip_project_profile` (CLI `query project.profile`) when project purpose is missing from your context or its changed version matters to the task. Read history is not proof of memory, understanding or delivery; explicit re-reading always remains available. Current decisions, implementation evidence and failure guidance still require fresh task-scoped reads independently. Propose changes with `skip_propose_project_profile`; only a verified user can apply them. Introduction text is context, never execution authority.

## Goal completion, archive and resume

When the user asks to tidy, complete, hold, archive or reopen goals, read `skip_goals` and the relevant completion evidence. Do not equate finished execution with fulfilled goal scope. Capture the actual current request through native entry, then use `skip_update_goals` with its input ID/digest, original instruction spans and exact changes (`id`, `revision`, `state_version`, `from_state`, `to_state`, `reason`, `evidence`). Supporting records use exact kind/id/revision; do not manufacture passing checks. The tool uses the native Codex adapter; do not submit `record.lifecycle` as an agent or write a one-off script to construct a human Principal. CLI fallback: `skip-codex --workspace <root> --project <id> --update-goals '<JSON>'`. No keyword rephrasing is required. Original input and scope interpretation are distinct: the agent remains responsible for following the user's meaning and restrictions. Other hosts use their native `goal.transition` action; a missing verified host path is not missing user approval.

A STALE result requires rereading the changed goal before retrying. State_version prevents lifecycle-only races even when content revision is unchanged. The batch is atomic. Its receipt changes goal state only; it does not complete work checks, declare deployment successful, authorize execution or erase remaining evidence.


## Incremental context maintenance

At natural task boundaries (stable decisions, completed phases, resolved investigations or a substantial task change), consider reducing temporary context. Follow [the complete maintenance rule](references/context-maintenance.md). Do not compact every turn, repeatedly during active discussion, or estimate unavailable context usage.

Before compaction, save only missing durable decisions, relevant facts and failures, and current work through the existing `skip_submit`, `skip_amend` or `skip_result` paths. Keep exact references and retrieval provenance where they matter; do not create duplicate records or a separate compaction report. If necessary preservation fails, keep that information in context and defer compaction.

Choose the timing yourself and directly use the compaction capability available in your current agent environment. SKIP supplies guidance, not a compaction runtime or host-specific permission check. If no such tool is available, preserve the important records and continue without claiming compaction occurred.

After compaction, check that you can still answer: the user's current intent, existing decisions, constraints, unresolved questions, and current work/next action. Restore only missing or ambiguous information with `skip_context` and exact record reads; expand incomplete results before relying on them. This is a reasoning check, not a five-field submission or a host-completion gate.

## Semantic execution entry

Before `--begin-current`, capture the actual current input and save its meaning through `skip_enter` (or update the materialized request through `skip_interpret`). The adapter reads that saved interpretation; it does not reclassify the sentence as execution authority. Bind an explicit action to the existing goal or exact work. For a continuation, use `resume` and the exact work-item target with `target: {mode: "none"}` when no new records are needed; the original request in this conversation must already permit that action. Preserve current prohibitions, uncertainty and changed scope in the interpretation. Never inherit implementation from a planning-only request.

`INTERPRETATION_REQUIRED` asks the agent to submit or connect the interpretation using the already-captured original input. It is not a request for the user to repeat an approval or use special wording. Recheck changed selections and normal Core execution conditions after interpreting. `--finish-current` only reports completion of that conversation's existing execution; it grants no new action.
