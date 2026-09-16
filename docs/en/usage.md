# Installation and usage

[SKIP](../../README.en.md) · [Concepts and decisions](concepts.md) · [Architecture and runtime](architecture.md) · [Paseo plugin](paseo.md) · [Verification and limits](verification.md)

## Source checkout

Linux is the verified source-checkout environment. Python 3 and Git are required; the Core runtime uses Python's standard library and SQLite. A source checkout does not install a hosted service or replace the user's IDE.

Install into the per-user `.agents/skills` directory described in the [official Codex skill documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills). Use an unused destination:

```bash
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/msang710/SKIP.git "$HOME/.agents/skills/skip"
```

Codex detects skill changes automatically; restart it if the skill does not appear. Existing active sessions may still need a fresh task to use updated instructions.

### Windows

The packaged Windows path uses SKIP's bundled Python/runtime rather than requiring the target user to install Python, SQLite, npm, or Git for normal packaged use. Windows installer acceptance remains separate from package construction and automated checks; see [Core development status](db-core.md).

Native source execution on Windows/macOS has not been qualified unless explicitly described in the current validation docs.

## Use from an agent conversation

The current skill identifier is `$skip`.

With no arguments it behaves like help and should not create a goal:

```text
$skip --help
```

For meaningful work, describe the desired behavior and scope rather than implementation file names:

```text
Use $skip to investigate releasing reserved inventory on order cancellation.
Clarify exceptions for orders where packing has started.
Show the plan and do not implement before my approval.
```

A fresh session that is resuming existing work should identify the existing goal and read fresh bounded context before relying on conversation memory.

When SKIP MCP tools are connected, the agent should prefer them for normal reads and writes. Common tools include `skip_status`, `skip_context`, `skip_decisions`, `skip_submit`, `skip_amend`, `skip_result`, `skip_learning`, and `skip_execution_status`.

## Local CLI and development entry points

The installed launcher resolves the local Core and project identity. For example:

```bash
skip --workspace <project-root> query status
```

The source-development fallback is the Core module CLI:

```bash
python -m skip_core.cli --project <project-id> query status
python -m skip_core.cli --project <project-id> query context --input '{"goal_id":"<goal-id>"}'
```

The Codex native adapter reads the actual current host turn when provenance or execution authority is required:

```bash
python -m adapters.codex.entry --workspace <project-root> --project <project-id> --goal <goal-id>
```

Do not use retired `scripts/intent_context.py` or file-based runtime writers after deployment. See the [Core contract](../../references/db-core-contract.md) for the authoritative current commands and boundaries.

## Records and privacy

SQLite is the sole runtime business-record store.

On Linux the default data root is:

```text
~/.local/share/SKIP
```

or `$XDG_DATA_HOME/SKIP` when that variable is set. The default database file is `skip.db`. `SKIP_DATA_ROOT` can select an explicit host data root. Other platforms use their documented platform-local data locations.

The database stores goals, decisions, selections, requirements, plans, work items, evidence, learning records, settings, provenance, and current facts through typed revisions and relationships. Product source code remains in the product repository; SKIP does not maintain a parallel Markdown/JSON/YAML business store or a `NOW` directory.

Historical records may contain detailed development history and should be treated as private project data unless deliberately prepared for publication. Imported historical material remains history: retrieval does not turn it into fresh approval, current-source evidence, or current execution authority.

A public distribution of SKIP ships workflow code, documentation, tests, and synthetic examples. Original project records stay private. Real-document excerpts should be published only after reviewing their disclosure scope, as in the [QuickHack case study](../../examples/quickhack/README.md).

## Updating and recovery

Core schema upgrades are explicit. Upgrade a candidate database first; do not run an older writer against a newer schema or silently replace a live database in response to an error.

`Database.backup` uses SQLite's backup API and checks integrity. Restore rehearses recovery into a new file rather than overwriting and activating an existing database automatically. See [Core development status](db-core.md) and the [Core contract](../../references/db-core-contract.md) for current recovery behavior.
