# Architecture and runtime

[SKIP](../../README.en.md) · [Concepts and decisions](concepts.md) · [Installation and usage](usage.md) · [Paseo plugin](paseo.md) · [Verification and limits](verification.md)

## Current workflow

For material changes, the current skill follows this general path:

1. Capture the actual current user request and its verified origin when the host supports it.
2. Identify or create the exact goal without inventing one from repository state or conversation memory.
3. Read fresh bounded context for that goal.
4. Inspect current repository behavior and affected paths.
5. Separate facts, assumptions, gaps, product decisions, and design choices.
6. Resolve genuine PRODUCT decisions with the user.
7. Draft requirements and observable acceptance criteria.
8. Design the implementation and relevant failure/recovery behavior.
9. Create executable work items linked to exact requirement/plan/decision revisions.
10. Begin material execution only through the current host's verified authority path.
11. Run proportionate verification and record evidence against exact source/work references.
12. Report result / checks / remaining work while preserving FAIL, NOT_RUN, STALE, BLOCKED, incomplete context, and unresolved gaps.

Narrow, reversible changes may use a compact flow. Material business rules, permissions, inventory, money, persisted data, recovery, and external-state changes require proportionate risk, design, and verification.

## Runtime model

| Component | Current behavior | Boundary |
|---|---|---|
| **Skill instructions** | FACT / PRODUCT / DESIGN separation, continuity rules, proportional workflow and reporting | Instructions guide the agent; they do not physically intercept host writes |
| **Shared SQLite Core** | One source of truth for business records, revisions, relationships, provenance, authority state and evidence | No parallel Markdown/JSON/YAML runtime business store |
| **Typed immutable revisions** | Goals, decisions, requirements, plans and work use exact revision-qualified relationships | Publishing/sealing content is not itself human approval |
| **Bounded context queries** | Retrieve goal/stage-specific records, selections, failures, guidance and current facts within explicit budgets | Incomplete packs must not be treated as complete knowledge |
| **Entry/provenance** | Native adapters can bind the actual current host turn to an input/request/interpretation | Unsupported hosts may read/propose but cannot fabricate verified user provenance |
| **Execution authority** | Re-checks current request, source snapshot, policy, risk and exact record revisions before material execution | Planning approval does not imply implementation or deployment approval |
| **Evidence and assurance** | Records PASS/FAIL/NOT_RUN, environment/boundary evidence, failure attempts, guidance and assurance obligations | Agent-reported evidence is not upgraded to a host observation |
| **MCP** | Exposes the same Core through read/write/query tools and decision UI resources | Generic MCP access does not authenticate a human approval or verified user turn |
| **Native adapters / UI** | Codex and Paseo integrations connect current host/session/UI context to the shared Core | Live host/workspace/agent/thread handles remain ephemeral and adapter-owned |

## Continuity across sessions and agents

SKIP treats the conversation as a disposable working context, not long-term project storage.

```text
Session A ─┐
Session B ─┼──→ shared SQLite Core ──→ bounded context ──→ current agent
Agent C   ─┘
```

Durable records preserve the information that a fresh session cannot safely reconstruct from source code alone: product intent, decision rationale, selected options, requirements, rejected or superseded records, plans, work, failures, evidence, and unresolved gaps.

The goal is not to replay every historical token. Context queries select only the records relevant to the current goal/stage, and the skill expands incomplete results when omitted information matters.

Historical context is also not treated as live truth. A retrieved decision can still be valid while an old repository observation is stale. Current source, selections, policy, evidence, and execution basis are re-checked where required.

## Entry, interpretation, and authority

A user sentence, a saved request, a selected record, and an execution authorization are different things.

Native entry captures the actual host input before materialization. The agent may propose a structured interpretation tied to exact instruction spans and targets, but parser suggestions and agent-written JSON never create human authority.

```text
actual host input
      ↓
verified input envelope
      ↓
agent interpretation
      ↓
goal / records / work
      ↓
current execution checks
      ↓
material action
```

Reading a record or attaching it to a composer is context only. A plan request stays a plan. A later implementation request may authorize previously prepared work, but the execution path re-checks exact work, source and policy state rather than rewriting history to manufacture permission.

Unknown delivery is not automatically retried into another session. Plans and durable records are portable; live routing handles are not.

## Core queries and entry points

Prefer connected MCP tools during normal agent use. Representative tools include:

```text
skip_status
skip_context
skip_decisions
skip_submit
skip_amend
skip_result
skip_learning
skip_execution_status
```

The installed local launcher can query the same Core:

```bash
skip --workspace <project-root> query status
```

Source-development fallback uses the module CLI:

```bash
python -m skip_core.cli --project <project-id> query context --input '{"goal_id":"<goal-id>"}'
```

The Codex native adapter provides current-turn provenance and current-execution entry when available:

```bash
python -m adapters.codex.entry --workspace <project-root> --project <project-id> --goal <goal-id>
```

Do not use retired `scripts/intent_context.py` or file-based runtime writers after deployment. The authoritative command and schema behavior lives in [the Core contract](../../references/db-core-contract.md).

## Storage and revision model

SQLite is the sole runtime business-record store. The Core uses immutable/sealed revisions, exact foreign-key relationships, transactional commands, CAS/idempotency, bounded queries, and explicit schema upgrades.

A changed decision, requirement, plan, source basis, or policy does not silently inherit authority from an older revision. Current projections expose selection and staleness state rather than asking the model to infer them from record order.

Imported historical records may preserve original text and relationships, but historical status does not become current approval or verification. Old file-runtime material remains recovery/regression provenance, not a second live writer.

## Failure learning and verification

Routine FAIL evidence remains evidence. Significant failures may additionally create typed failure/attempt records and later guidance. Assurance queries connect relevant environments, scenarios, obligations, evidence, and exceptions so a passing result in one boundary is not silently generalized to another.

Examples of deliberately separate boundaries include:

- unit/integration test vs packaged runtime,
- mock DB vs real database competition,
- VM vs physical hardware,
- agent report vs host observation,
- implementation completion vs deployment acceptance.

Current-source verification is therefore part of continuity: memory can explain why the project reached a state, but memory alone does not prove that the state still exists.

## Integration and enforcement boundaries

The current Core and MCP are implemented in development, including bounded queries, immutable revisions, transactional commands, backup/restore, official MCP SDK integration, current-turn Codex provenance, and the Paseo current-agent/decision surfaces.

Important boundaries remain:

- Enforcement is **advisory**; SKIP does not intercept arbitrary host writes or provide same-OS-user privilege isolation.
- Generic MCP support alone does not authenticate human approval or start a verified agent turn.
- Hosts without exact-message receipt lookup cannot automatically resolve uncertain delivery.
- The Paseo public adapter does not provide atomic idle-conditioned sends or confirmed interruption.
- Automated/package checks do not establish live Windows installer acceptance, live Paseo acceptance, device acceptance, or production acceptance unless those surfaces were actually tested.

See [Shared SQLite Core — development build](db-core.md) and [Verification and limits](verification.md) for the current validation status.
