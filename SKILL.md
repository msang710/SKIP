---
name: skip
description: Supervise coding work through current evidence, explicit product decisions and a shared SQLite Core. Use for meaningful feature planning, business rules, implementation and restoring an existing SKIP goal. Keep the user's IDE and agent; adapt procedure to failure cost. Skip trivial self-contained edits unless explicitly invoked.
---

# SKIP

Read the decisions. Skip the implementation details.

Use the current user's language. Keep FACT (observed), PRODUCT (human policy) and DESIGN (technical choice) distinct. Use the existing agent and IDE. Do not ask users to operate a documentation workflow.

## First entry

- With no request, show short help. Do not create a goal.
- Start from this actual user request. Never invent past goals from code, Git, conversation summaries or agent memory.
- Prefer the host's connected SKIP MCP tools. `skip_status` reads current facts; `skip_context` reads one explicit goal and stage. An incomplete pack is not enough to infer missing decisions or approvals.
- In Codex with local session provenance, the bundled `adapters.codex.entry` reads the current actual user turn. `--activate` connects the project with no goals; a subsequent request creates only the needed goal. Use `--goal` to continue an existing goal. A generic continuation/status request does not invent a new goal.
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

## Verify and report

Keep source, unit/integration tests, package, installation, runtime and visual/device evidence distinct. Evidence submitted by the model is `agent_report`; never upgrade it to a host observation. Execution finish is not proof that required checks passed.

Record results against exact source snapshots and work/criterion IDs. NOW is a Core query of current facts and their evidence, not a file to refresh. Preserve FAIL, NOT_RUN, incomplete context and stale evidence.

Report **결과 / 확인 / 남은 일** (or equivalents in the user's language) briefly, with relevant record/source links. Describe what is implemented, what was actually tested and what remains unverified. Implementation does not authorize installation, restart, remote upload or deployment; evaluate those actions against the user's current authorization and the concrete target.

## Installed command paths

The installed skill root contains `skip_core`, `skip_mcp` and `adapters`. Run modules from that root or set `PYTHONPATH` to it; preserve the actual project directory with `--workspace`. The installed `skip` CLI resolves portable project identities from SQLite and accepts an explicit `--project` when needed. For example, `skip --workspace <actual-workspace> query status`. Its `command` action accepts the same agent command JSON on stdin and never grants human authority. `skip-mcp` runs the installed official stdio server. Do not invoke retired `scripts/intent_context.py` or file-based runtime writers after deployment.
