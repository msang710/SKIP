# SKIP artifact contract

## Goal authority state

New decision-runtime goals may contain `.skip/ledger/*.yaml` and `.skip/projection.yaml`. Ledger events are immutable authority records scoped to that goal. The projection is a disposable cache and must not override artifact bytes or current source evidence. Existing goals without `.skip/` remain read-only until explicitly initialized; selection and context compilation never create runtime state.

## Location and metadata

Store artifacts outside the product repository under:

```text
<record-root>/projects/<project-id>/features/<feature-slug>/
```

Reuse an existing feature folder and create only files needed for the current stage. Do not fall back to a product-local `specs/` directory unless the user explicitly overrides the external-store contract.

Start each new artifact with:

```yaml
---
schema: skip-artifact/v1
artifact: <impact | prd | user_stories | system_design | tasks>
id: <feature-slug>
project_id: <project-id>
title: <feature title>
status: <draft | draft-with-open-questions | approved>
review:
  verdict: <ready | needs-work>
  purpose: <short-stable-token>
implementation:
  gate: <ready | blocked>
  reason: <short-stable-token>
decisions:
  confirmed: [<decision IDs>]
  open: [<decision IDs>]
created: <YYYY-MM-DD>
updated: <YYYY-MM-DD>
source_revision: <commit, revision, uncommitted, or unversioned>
source_id: <declared source id>
source_root: <source root relative to the logical workspace, normally .>
output_language: <language code>
---
```

Structured frontmatter is authoritative for artifact type, lifecycle status, review verdict, implementation gate, and decision state. Keep only IDs in `decisions`; keep meaning and rationale in Markdown. Human-readable verdict/gate lines are projections and must agree with frontmatter. Fail closed on malformed structured metadata or conflicts.

Legacy artifacts without `schema: skip-artifact/v1` remain valid through the compatibility body reader. Do not bulk migrate them. Convert one only during an otherwise material update. Heading language and table layout must not determine machine state for structured artifacts.

When an artifact spans multiple sources, replace `source_revision`, `source_id`, and `source_root` with a `source_revisions` mapping keyed by declared source ID. Qualify cross-source evidence paths as `<source-id>:<relative-path>`.

Record approval evidence in the decision log: date, summarized user wording, approved artifacts, and scope. Do not interpret an ambiguous request to continue as approval.

Artifact status, review readiness, and implementation authorization are different:

- `status` describes the artifact lifecycle.
- `Review verdict` describes readiness for the named review purpose.
- `Implementation gate` remains `BLOCKED` until required decisions, requirements, design, tasks, and prerequisites have explicit approval.

Use source-relative paths in portable artifacts. Keep machine-specific runtime bindings in the local registry only.

## `impact.md`

Include investigation boundary, current flow, evidence, impacted and evidenced-unaffected areas, data and permission impact, operations, compatibility, and uncertainty.

| Claim | Classification | Path or symbol | Evidence | Confidence |
|---|---|---|---|---|
| Current behavior | FACT / INFERENCE / GAP | Relative file, symbol, test, or command | Observation | high / medium / low |

## `prd.md`

Include goal, problem and users, current and target behavior, symmetric scope and non-scope, product rules and exceptions, decision log, open questions, measurable success criteria, compatibility, rollout, and risks.

| ID | Date | Classification | Decision | Evidence and rationale | User or operational impact | Status |
|---|---|---|---|---|---|---|
| D-001 | YYYY-MM-DD | PRODUCT | Selected rule | Facts and goal | Observable difference | confirmed / open |

Connect every product rule to an observable acceptance criterion. Give numeric targets a baseline and measurement method.

## `user_stories.md`

For each story include ID, actor/action/value, connected decision, normal flow, relevant empty/permission/duplicate/partial-failure/recovery paths, independent Given/When/Then criteria, and observable completion.

For money, quantities, inventory, deletion, and permissions, include boundaries and failure invariants.

## `system_design.md`

Include goals, non-goals, approved inputs, current and target flows, exact file and symbol candidates, contracts, data and migration, authorization, failure/retry/idempotency/concurrency, observability and sensitive-data handling, test traceability, rollout, compatibility, rollback, recovery, alternatives, and open risks.

| Requirement | Design element | Verification | Residual risk |
|---|---|---|---|

Return any design choice that changes product behavior to the PRD as an open decision.

## `tasks.md`

Create tasks only from approved design:

New full-workflow tasks begin with a `Human Plan Review` covering observable change, preserved invariants, facts, decisions, design commitments, challengeable assumptions, stable checkpoints, failure/rollback, completion evidence, approval scope, excluded authority, and user confirmation needs. Compact flow and legacy tasks remain valid without it.

```markdown
## T-001 <task title>

- Purpose:
- Dependencies:
- Target files or symbols:
- Change:
- Completion conditions:
- Verification:
- Connected requirements:
- Stable state after completion:
- Compatibility maintained:
- Activation/switch point:
- Rollback point:
- Atomic with: <task IDs | none>
```

Order tasks by actual dependencies and valid, testable system boundaries rather than work volume. If no safe intermediate state exists, declare the exact atomic span, containment, and recovery. Do not use vague tasks such as only `implement` or `add tests`.
