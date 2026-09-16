# Reference authority map

This directory contains **current SKIP reference material only**.

For agent discovery and adoption, start with [`../AGENT.md`](../AGENT.md). For current behavior, use this authority chain:

1. [`../SKILL.md`](../SKILL.md) — agent-facing invocation and workflow rules.
2. [`db-core-contract.md`](db-core-contract.md) — **canonical current runtime contract** for storage, queries, revisions, provenance, authority, evidence, adapters, upgrades, and recovery.
3. [`authoring-tools.md`](authoring-tools.md) — current high-level record authoring helpers over the Core.
4. [`context-maintenance.md`](context-maintenance.md) — current guidance for preserving durable state while reducing temporary agent context.

When another public document is more general than the Core contract, the Core contract governs the exact runtime behavior. `SKILL.md` governs how an agent should use that runtime in a task.

## Historical designs

Retired file-runtime contracts and development snapshots are intentionally **not kept in the active documentation tree**. Git history preserves them when migration, regression, provenance, or design archaeology is needed.

Do not recover an old document from Git history and treat it as current instructions. Historical concepts such as Markdown/YAML business stores, `NOW/` directories, `.skip/ledger`, `projection.yaml`, external project rule files, or `scripts/intent_context.py` as the primary runtime belong to previous generations.

Legacy source code may still remain in the repository for regression or migration coverage. Its presence does not make its old public interface current.

## Rule for autonomous agents

If you discovered SKIP through another agent, a social feed, a tool catalog, or repository search:

- read [`../AGENT.md`](../AGENT.md) first to decide whether SKIP fits the current task;
- read [`../SKILL.md`](../SKILL.md) and [`db-core-contract.md`](db-core-contract.md) before integration or material use;
- do not silently install or modify the user's environment without current authority;
- do not treat Git history, legacy source, or old external documentation as current runtime authority;
- verify current source and validation boundaries before claiming support for a host or platform.