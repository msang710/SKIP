# Concepts and decisions

[SKIP](../../README.en.md) · [Architecture and runtime](architecture.md) · [Installation and usage](usage.md) · [Paseo plugin](paseo.md) · [Verification and limits](verification.md)

## Why SKIP exists

Coding agents can already write more code than many users can realistically review.

A person may know exactly how their work should behave while having no idea which class, worker, API, migration, query, event, or state machine controls that behavior.

That person can say:

> Reserved stock must not be sellable.
> Cancelling an order should release it.
> But if a shipping label already exists, do not release it automatically.

They may not be able to say:

> Change `ReservationService`, add a migration, update these two callers, and make this worker idempotent.

**They should not have to.**

SKIP exists to preserve the first kind of knowledge while letting the coding agent handle the second.

```text
You know what should happen
          ↓
SKIP investigates what currently happens
          ↓
Unknown product choices are surfaced to you
          ↓
You decide the outcome
          ↓
The agent designs and implements it
          ↓
The result is verified
          ↓
Project memory survives for the next agent
```

## What you can skip — and what you cannot

```text
Repository archaeology          → skip
Caller tracing                  → skip
Implementation details          → skip
Most technical design prose     → skip
Most generated documentation    → skip

Your intent                     → NEVER SKIP
Product decisions               → NEVER SKIP
Meaningful approval             → NEVER SKIP
Known risks and blockers        → NEVER SKIP
Verification result             → NEVER SKIP
```

The point is not to remove the human from development.

The point is to move the human to the layer where human judgment is actually valuable.

## You still need to know what you want

SKIP does **not** solve vague intent.

> **You do not need to know how to build it. But you do need to know what you are trying to build.**

"Make me an inventory app" is not enough to guarantee a good system.

"Reserved stock must never be allocated twice, failures must be traceable, and only an authorized operator may reverse a finalized state" is something SKIP can work with.

The better you understand the desired outcome, the more useful the workflow becomes.

## The failures SKIP is designed against

### 1. Silent product decisions

Without an explicit decision layer, AI development can look like this:

```text
Human intent
    ↓
Incomplete request
    ↓
Agent silently fills the gaps
    ↓
Plausible implementation
    ↓
Later: "Why does it work like this?"
```

SKIP changes the middle:

```text
Human intent
    ↓
Repository-grounded investigation
    ↓
FACT / PRODUCT / DESIGN separation
    ↓
Unresolved PRODUCT decisions return to the human
    ↓
Approval
    ↓
Design
    ↓
Implementation
    ↓
Verification
```

The coding agent may decide *how* to implement an approved result.

It may not silently decide *what result the user should get*.

### 2. Session amnesia

A long-running project should not depend on one chat window remembering everything.

A fresh conversation may contain the same model and the same repository, yet it does not automatically inherit every decision, correction, rejected alternative, implementation checkpoint, or piece of context from the previous session. Switching to another coding agent makes that boundary even more obvious.

> **A new chat is a new coworker. The project should not have to start over.**

SKIP therefore treats useful project memory as something that belongs **outside the conversation**.

```text
Session A ─┐
Session B ─┼──→ records / decisions / NOW ──→ bounded selection ──→ current agent
Agent C   ─┘
```

The goal is not to preserve an AI personality.

The goal is to preserve the **project's continuity** across disposable sessions and interchangeable agents.

### 3. Context dumping

Keeping memory is not enough. Giving every historical document to every session creates a different failure:

> Too little history → the agent forgets why the system exists.
> Too much history → context becomes expensive, noisy, stale, and contradictory.

SKIP stores history separately and selects only the records needed for the current task.

### 4. Human attention spent at the wrong layer

If a non-developer has to read every generated design document or every changed source file, the workflow has failed to create useful abstraction.

SKIP keeps detailed evidence for the agent while reducing human review to the decisions, claims, risks, and outcomes that actually need human judgment.

## FACT, PRODUCT, DESIGN

SKIP separates three kinds of claims that coding agents often blur together.

### FACT

What the current system actually does.

Source code, schemas, migrations, tests, configuration, revision state, and observed execution are evidence. Unverified claims remain assumptions, inferences, gaps, or `EVIDENCE_PENDING`.

### PRODUCT

A choice that changes the result experienced by a user or operator.

Examples include access, permissions, state transitions, money, quantities, inventory behavior, cancellation, deletion, failure, recovery, compatibility, and operational policy.

These decisions belong to the human.

### DESIGN

How the approved product result is implemented.

Examples include file and component boundaries, APIs, schemas, algorithms, migrations, retries, idempotency, concurrency, observability, tests, rollout, and rollback.

These decisions normally belong to the agent when they preserve the approved outcome.

## Approval is not documentation theater

SKIP can generate:

```text
impact.md
prd.md
user_stories.md
system_design.md
tasks.md
```

You can read all of them.

You usually do not need to.

Their primary job is to give the next reasoning step — and the next session — enough structured context to avoid rediscovering, forgetting, or mutating earlier decisions.

A human-facing review should instead look closer to this:

```text
What changes
- Reserved stock will no longer be considered shippable.

Decision needed
- What should happen after label issuance but before carrier submission succeeds?

Recommendation
- Keep the reservation until the shipment is explicitly voided.

Risk
- Releasing early can double-allocate inventory.

Verification
- PASS: allocation and cancellation regression tests
```

**Read the decisions. Skip the implementation details.**

## Long-term project memory

Historical records answer:

> Why did we make this decision?

`NOW` answers:

> What is currently implemented?

The current implementation supports bounded selection by project, date, goal, artifact, decision, and current-state view.

```text
$skip --now
$skip --260825
$skip --goal stock-allocation
$skip --focus decisions
$skip --setup
```

Selection is fail-closed: an empty result is not silently widened into "read everything".

`--setup` shows the ten default collaboration rules and project-specific rules. It previews an exact change before anything is stored; only explicit approval may apply it.

The deterministic selection logic lives in `scripts/intent_context.py` rather than being improvised by the model on every run.

### `NOW` is useful — but it is not truth

`NOW` is a compact, replaceable routing view of verified current implementation state.

It is intentionally **not** treated as independent proof.

If a claim matters to the current task, SKIP re-checks the repository, tests, schemas, configuration, or observed execution before trusting it.

```text
Historical records
        ↓
       NOW
        ↓
bounded context selection
        ↓
current repository verification
```

Memory should survive sessions without becoming mythology.

## Cost model

Reducing the agent's token usage is **not SKIP's goal**.

SKIP should still avoid irrelevant context, unnecessary repeated investigation, and wasteful retrieval. Efficiency matters. But token usage is something to optimize, not the objective that defines the workflow.

When additional context is needed to preserve intent, surface decisions, verify repository reality, or carry project memory safely across sessions, SKIP is willing to spend it.

A full workflow may be unnecessary for a tiny reversible change. For permissions, inventory, money, destructive actions, persisted state, migrations, external integrations, concurrency, rollback, and business rules, the additional context can be worth the cost.

> **SKIP uses context as efficiently as it can, but it does not trade away semantic safety just to minimize tokens.**

## Limits

SKIP does **not** increase the underlying agent's physical reasoning capacity, context window, or inherent output quality.

A smaller or weaker model can still make incorrect inferences while following SKIP. The workflow itself also consumes context for investigation, records, decisions, design, and verification, so SKIP can sometimes push an agent closer to its context limit rather than farther away from it.

SKIP does not remove those limits.

What it can do is put boundaries around their consequences.

> **The goal is to stop a model limitation before it becomes unverified code or reaches a running service.**

Repository evidence, explicit uncertainty, approval gates, and verification exist so questionable reasoning has places to stop before it becomes an authorized implementation or operational change.

If the agent cannot establish sufficient evidence within its reasoning or context limits, the correct outcome is to stop with a named gap or `EVIDENCE_PENDING` — not to manufacture confidence.

## Who this is for

SKIP is especially useful for:

- domain experts building tools for their own work ([QuickHack example](../../examples/quickhack/README.md)),
- operators and analysts automating business processes,
- non-traditional developers working with coding agents,
- solo builders who can define desired behavior more easily than architecture,
- long-running projects where intent and decisions need to survive beyond one conversation or one agent.

## Who this is not for

If you can already say:

> Change this object, replace this interface, add this migration, and update these callers.

then SKIP may feel unnecessarily slow.

You already possess the implementation-level map that SKIP spends time reconstructing and validating. Direct coding-agent instructions may be faster and cheaper.

## Philosophy

Coding agents are making code generation less scarce.

That does not make product judgment, domain knowledge, or clear intent less important. It makes them more important.

The hard question is no longer only:

> **Can the AI write the code?**

It is increasingly:

> **Can the human's original intent survive the trip from an imperfect request to verified implementation — and survive the next conversation too?**

SKIP exists for that problem.

> **Skip the code. Skip most of the documents. Skip the implementation details.**
> **Do not skip the intent. Do not lose the memory.**
