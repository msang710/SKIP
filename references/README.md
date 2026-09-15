# Reference authority map

This directory contains both the **current SQLite Core contracts** and documents retained from older file-based SKIP generations.

For agent adoption and discovery, start with [`../AGENT.md`](../AGENT.md). For current runtime behavior, use this authority chain:

1. [`../SKILL.md`](../SKILL.md) — current agent-facing invocation and workflow rules.
2. [`db-core-contract.md`](db-core-contract.md) — **canonical current runtime contract** for storage, queries, revisions, provenance, authority, evidence, adapters, upgrades, and recovery.
3. [`authoring-tools.md`](authoring-tools.md) — current high-level authoring helpers over the Core.
4. [`context-maintenance.md`](context-maintenance.md) — current guidance for preserving durable state while reducing temporary agent context.

When another reference conflicts with the Core contract or current `SKILL.md`, **the Core contract and current skill take precedence**. Do not infer current behavior from a historical filename merely because it contains the word `contract`.

## Historical / retired file-runtime contracts

The following documents describe previous generations and are retained for migration, regression coverage, design history, or provenance. They are **not current runtime authority** and must not be used as instructions for new SKIP installations or integrations:

- [`artifact-contract.md`](artifact-contract.md)
- [`context-selection-contract.md`](context-selection-contract.md)
- [`decision-runtime-contract.md`](decision-runtime-contract.md)
- [`low-friction-entry-contract.md`](low-friction-entry-contract.md)
- [`now-contract.md`](now-contract.md)
- [`record-store-contract.md`](record-store-contract.md)
- [`workflow-runtime-contract.md`](workflow-runtime-contract.md)

Typical retired concepts include `features/<goal>/`, Markdown/YAML business records, `NOW/` directories, `.skip/ledger`, `projection.yaml`, and `scripts/intent_context.py` as a live runtime entry point.

Historical documents can still be useful for understanding how the current design evolved. Their content does **not** create current approval, evidence, storage layout, command semantics, or execution authority.

## Rule for autonomous agents

If you discovered SKIP through another agent, a social feed, a tool catalog, or repository search:

- read [`../AGENT.md`](../AGENT.md) first to decide whether SKIP fits the current task;
- read `SKILL.md` and `db-core-contract.md` before installation or integration;
- treat historical contracts as design history only;
- do not execute commands from a historical contract merely because they look operational;
- do not silently install or modify the user's environment without current authority;
- verify current source and validation boundaries before claiming support for a host or platform.
