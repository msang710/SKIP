# SKIP review checklist

Run this checklist before requesting approval or claiming readiness. Add a short `Self-review` section to the reviewed artifact and end with a review verdict and a separate implementation gate.

## Evidence and scope

- Was the project and external record root resolved without ambiguity?
- Was project/goal/scope identified before selected records were expanded, with the full manifest retained in structured/detail output?
- Were zero-result or conflicting filters handled without widening scope?
- Is every important current-state claim supported by code, schema, migration, test, configuration, revision state, or execution?
- Are facts separated from inferences, assumptions, and gaps?
- Were callers, reads, writes, permissions, async work, integrations, failure handling, and relevant tests traced?
- Are documentation and executable-code conflicts recorded?
- Does every `unaffected` conclusion have evidence?
- Are unrelated worktree changes identified and preserved?
- Was every material user FACT counterclaim reinvestigated against current code and executable evidence at planning depth?
- Are completion claims proven on the same evidence surface they describe?

## Product clarity

- Is the goal an observable user or operational result rather than an implementation technique?
- Are scope and non-scope consistent?
- Are roles, permissions, state transitions, failures, recovery, cancellation, deletion, money, quantities, and inventory covered where relevant?
- Are user questions limited to actual `PRODUCT` decisions?
- Does each decision include a recommendation, evidence, and outcome difference?
- Are unsupported targets and hidden policies removed?
- Is every product rule connected to an observable acceptance criterion?

## Design completeness

- Are input requirements and their approval state explicit?
- Do proposed paths, symbols, types, endpoints, and commands exist or have verified naming precedents?
- Are data, API, event, and shared-type contracts concrete?
- Are authentication, authorization, and data-access boundaries clear?
- Are duplicate requests, retry, idempotency, concurrency, and partial failure covered where needed?
- Are migration, backfill, prior data, and backward compatibility addressed?
- Are logs, metrics, traces, audit data, and sensitive-data protections proportional to risk?
- Are rollout, rollback, and operational recovery defined?
- Did any design choice that changes product behavior return to the PRD?

## Tests and execution

- Were affected `NOW` claims refreshed only after proportionate verification?
- Does `NOW` contain current truth rather than plans or chronological history?
- Are stale, partially verified, physical-environment, and external-system limits explicit?
- Are normal, boundary, permission, failure, recovery, and regression scenarios included?
- Is every requirement traced to design and verification?
- Does every task name exact targets and completion conditions?
- Does task order reflect real dependencies?
- Were project-specific test, type, lint, build, migration, and verification commands discovered rather than assumed?
- Are skipped checks and residual risks explicit?
- Does structured artifact state agree with its Markdown projection?
- Does each implementation boundary leave a valid testable state, or declare an atomic span with containment and recovery?

## Verdict

- `READY`: the artifact is complete enough for its explicitly named current purpose, such as product-decision review or design approval. It does not by itself authorize implementation.
- `NEEDS_WORK`: a material product decision, unsupported claim, failure or migration path, verification gap, or executable-task gap remains.

Always report both:

```text
Review verdict: READY | NEEDS_WORK
Implementation gate: READY | BLOCKED — <reason or approval evidence>
```

Set the implementation gate to `BLOCKED` while any required product decision is open, requirements or system design lack explicit approval, tasks are provisional, or required pre-implementation validation is incomplete. Set it to `READY` only when the approved scope, requirements, design, tasks, and prerequisites are sufficient to begin implementation.

When the review verdict is `NEEDS_WORK`, fix what can be established from the repository and then present only the most important unresolved product decision. A draft may be `READY` for a user decision while its implementation gate remains `BLOCKED`.
