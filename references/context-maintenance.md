## Incremental Context Maintenance

Maintain working context continuously instead of waiting for context exhaustion.

### Principle

Prefer small, frequent compactions over rare, destructive compactions.

Context is a working set, not long-term storage.
Durable decisions, facts, failures, and completed work should live in SKIP records.
Keep the active context focused on what is still needed to reason about the current task.

### When to compact

Consider a light compaction when:

- a decision has become stable,
- a planning or implementation phase has completed,
- a question has been resolved,
- large logs, diffs, code excerpts, or tool output are no longer under active investigation,
- discussion has accumulated around alternatives that are no longer viable.

If the runtime exposes context pressure or remaining capacity, compact more proactively as pressure increases.
Do not invent or estimate context usage when the runtime does not expose it.

Do not wait for imminent context exhaustion unless no compaction capability is available.

### What to preserve

Preserve the highest useful fidelity for:

- the user's current intent,
- approved PRODUCT decisions,
- active requirements and acceptance criteria,
- architectural invariants and responsibility boundaries,
- unresolved questions,
- current task state and next actions,
- FACT evidence still relevant to an unresolved problem,
- exact errors still under investigation,
- file paths, symbols, commands, identifiers, and values whose exact form still matters.

Age alone is never a reason to discard information.

### What to compact first

Prefer reducing:

- rejected or superseded proposals,
- exploratory reasoning,
- resolved questions,
- abandoned implementation approaches,
- completed implementation chatter,
- verbose tool output whose conclusion is already known,
- repeated explanations of stable decisions,
- code or logs no longer needed verbatim.

For large evidence, preserve the conclusion and enough provenance to retrieve or verify the source again.

### SKIP record priority

Treat SKIP records as durable state:

- PRODUCT records preserve user-authority decisions and should rarely lose semantic detail.
- FACT records preserve current repository or runtime truth and supporting provenance.
- DESIGN records remain detailed while implementation depends on them, then may be reduced after implementation and verification.
- Exploration and transient reasoning should not become durable context unless they materially affect future work.

Before compacting information that may matter later, ensure its durable result is represented in the appropriate SKIP record.

### After compaction

After a meaningful compaction, ensure the working context still answers:

1. What is the user trying to achieve?
2. What has already been decided?
3. What constraints must not be violated?
4. What remains unresolved?
5. What is the current task and next action?

If any of these became ambiguous, restore the necessary information from SKIP before continuing.

### Safety rule

Never trade correctness for token reduction.

When uncertain whether information is still an active constraint, preserve it or externalize it to SKIP before reducing it.

### Compaction cadence

Do not compact on every turn.

Prefer event-driven compaction at natural task boundaries:
- after a decision becomes stable,
- after a task or implementation phase completes,
- after large diagnostic output is no longer needed,
- before starting a substantially different task.

Avoid repeated compaction during active back-and-forth work.

After a compaction, allow the working context to accumulate again before considering another one unless:
- context pressure is high,
- a very large transient payload was just consumed,
- or correctness is at risk from context exhaustion.
