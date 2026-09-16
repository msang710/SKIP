# Shared SQLite Core

[SKIP](../../README.en.md) · [Architecture and runtime](architecture.md) · [Installation and usage](usage.md) · [Paseo plugin](paseo.md) · [Verification and limits](verification.md)

SKIP has one runtime source of truth for business records: **SQLite through the Core application API**. There is no Markdown/YAML business-store fallback or dual writer in the active runtime.

Explanations remain human-readable text, while goals, decisions, selections, requirements, plans, work, evidence, learning, provenance, and lifecycle state use typed revision-qualified relationships. CLI, MCP, Codex integration, Paseo, and packaged entry points operate on the same Core model.

## Runtime principles

- Activation connects a project/source; it does not invent goals from code, repository names, or agent memory.
- New goals begin from actual user requests. Existing work resumes through an exact goal and fresh bounded context.
- FACT, PRODUCT, and DESIGN remain distinct. Product choices belong to the human; technical design can be delegated within the authorized scope.
- Goal/change risk, source snapshots, current record revisions, selections, policy, and provenance determine how much workflow is required.
- Historical records are durable context, not automatic current truth, approval, or verification.
- Execution completion and verification completion are separate states.
- Unknown delivery is not automatically replayed into another host/session.

## Current interfaces

| Surface | Role | Boundary |
|---|---|---|
| `SKILL.md` | Agent-facing workflow and invocation rules | Advisory instructions; no physical host-write interception |
| `skip_core` | Transactional application API, queries, revisions, authority, evidence, recovery | Sole live business-record writer |
| `skip_mcp` | Official MCP tools/resources over the same Core | MCP access alone does not establish human approval |
| Codex adapter | Current-turn provenance and native execution entry | Requires a verifiable current host session |
| Paseo plugin | Workspace/current-agent views and native UI interaction over the Core | Live routing handles stay adapter-owned and ephemeral |
| Windows bundle | Pinned Python + Core/MCP/UI/adapter package | Package construction is not installer/live-host acceptance |

## Storage and recovery

The data root is platform-local and outside the product repository. `SKIP_DATA_ROOT` can explicitly select a host data root; the default database is `skip.db`.

Schema upgrades are explicit. Upgrade and validate a candidate copy before any separately authorized cutover. Do not run an older writer against a newer schema or fall back to the retired file runtime.

SQLite backup uses the database backup API and integrity checks. Restore rehearses recovery into a new file; it does not silently overwrite or activate an existing database.

One-time historical migration is a maintenance operation. It may preserve original bytes, text, relationships, states, and provenance, but imported history does not gain fresh approval, selections, execution authority, or current-source evidence.

## Validation boundaries

Automated validation distinguishes Core tests, MCP protocol tests, UI/package construction, Paseo TypeScript/plugin checks, and Windows bundled-runtime checks from **live host, installer, GUI, device, and production acceptance**.

Passing CI is evidence only for the surfaces actually exercised by CI. Generic MCP support does not authenticate user approvals or create a verified host turn. Enforcement remains `advisory`; SKIP does not claim same-OS-user isolation or arbitrary host-write interception.

For the authoritative runtime contract, read [references/db-core-contract.md](../../references/db-core-contract.md). For the current CI surfaces and commands, read [Verification and limits](verification.md).