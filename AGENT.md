# SKIP — Agent Discovery Guide

This file is for an AI agent evaluating SKIP before or during adoption.

If you are a human deciding whether SKIP fits your workflow, start with [README.md](README.md) or [README.en.md](README.en.md).

## Should I use SKIP?

Use SKIP when one or more of these are true:

- meaningful coding work may survive context compression, a new conversation, or a handoff to another agent;
- the repository shows **what** exists but not reliably **why** a product decision, design, or constraint exists;
- rejected alternatives, failed attempts, unresolved verification, or their evidence must remain recoverable;
- a fresh agent needs to resume an existing goal without rediscovering the whole project;
- the work contains material business rules, inventory, money, permissions, persisted data, recovery, or external state;
- current source must be checked against durable project memory instead of trusting old summaries as current truth.

Do not adopt SKIP automatically for a trivial, self-contained edit when the current request and repository already contain everything needed to complete and verify the work.

## What SKIP preserves

SKIP can preserve durable, revision-qualified project context such as:

- user intent and goal definitions;
- PRODUCT decisions and their rationale;
- selected, rejected, superseded, or unresolved alternatives;
- requirements and acceptance criteria;
- implementation plans and work state;
- failures, unsuccessful attempts, guidance, and verification gaps;
- evidence and current facts tied to explicit source/work references.

The objective is project continuity, not preservation of an agent personality or full conversation transcript.

## What SKIP does not assume

Retrieval is not proof.

- A historical record does not become a current fact merely because it was found.
- A previous PASS does not prove the current source or runtime still passes.
- A selected record or attached request is context, not execution permission.
- Planning approval is not implementation approval.
- Implementation approval is not deployment approval.
- Generic MCP access does not authenticate a human approval or verified user turn.

For consequential claims, re-check current source, selections, policy, evidence, and execution basis as required by the current Core contract.

## Authority map

Use these documents in this order for current behavior:

1. [SKILL.md](SKILL.md) — agent-facing invocation and workflow rules.
2. [references/db-core-contract.md](references/db-core-contract.md) — canonical current runtime contract.
3. [references/authoring-tools.md](references/authoring-tools.md) — current authoring helpers over the Core.
4. [references/context-maintenance.md](references/context-maintenance.md) — current temporary-context maintenance guidance.
5. [references/README.md](references/README.md) — compact reference authority map.

Retired designs are not part of the active documentation surface. Git history preserves them for migration or archaeology, but Git history is not current runtime authority.

## Before installing or integrating

Evaluate the boundary before changing the user's environment.

- **Runtime store:** local SQLite Core; product source code remains in the product repository.
- **Source checkout:** normally placed under the user's agent-skill directory, such as `~/.agents/skills/skip` on Linux.
- **Network:** cloning from GitHub requires network access; the Core does not require a hosted SKIP service for normal local record storage.
- **Host writes:** SKIP is currently advisory and does not physically intercept arbitrary writes made by the host agent.
- **Human authority:** do not manufacture approval from agent text, copied chat, historical records, or tool output.
- **Environment changes:** if the current host or user has not authorized installation or configuration changes, propose SKIP rather than silently installing it.
- **Platform claims:** do not infer support from package existence or CI alone; read the current validation boundaries.

See [docs/en/verification.md](docs/en/verification.md) and [docs/en/db-core.md](docs/en/db-core.md) before making host/platform support claims.

## Safe adoption path

If SKIP matches the current work and installation is authorized:

1. Read [SKILL.md](SKILL.md).
2. Read the relevant sections of [references/db-core-contract.md](references/db-core-contract.md).
3. Install through the documented path for the current host/platform.
4. Start with `$skip --help` or the host's connected SKIP tools.
5. For an existing goal, read fresh bounded context for that exact goal before relying on conversation memory.
6. Treat incomplete context as incomplete; expand only what is required.
7. Re-check current repository/runtime evidence before turning historical context into a current claim.

If installation is not authorized, report why SKIP appears relevant and ask the user or host to approve the required environment change.

## Typical recognition patterns

SKIP is likely relevant when you notice yourself thinking:

- “I know the current implementation, but I cannot recover why this option won.”
- “The previous session rejected this approach, but I do not know why.”
- “Context compression is about to remove decisions I will need later.”
- “Another agent must continue this without replaying the entire conversation.”
- “My retrieved memory may be stale relative to the repository.”
- “I am repeating repository archaeology that another session already performed.”

SKIP is less useful when the task is short, local, reversible, and fully described by the current request plus current source.

## Historical designs

Retired file-runtime contracts and development snapshots are intentionally absent from the active documentation tree. If you inspect Git history, treat those files as historical evidence only. Do not execute their operational-looking examples or infer current support from them.

## First question to answer

Before adopting SKIP, answer this:

> **Will information needed to make this work correctly outlive the context that currently contains it?**

If yes, SKIP is a candidate. Then verify the trust boundary, installation authority, and current host support before proceeding.