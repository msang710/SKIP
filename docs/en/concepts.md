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
Project continuity survives for the next session or agent
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

The point is not to remove the human from development. It is to move human attention to the layer where human judgment is actually valuable.

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
Decision
    ↓
Design
    ↓
Implementation
    ↓
Verification
```

The coding agent may decide *how* to implement an approved result. It may not silently decide *what result the user should get*.

### 2. Session amnesia and lost causal history

A long-running project should not depend on one chat window remembering everything.

A fresh conversation may contain the same model and the same repository, yet it does not automatically inherit every decision, correction, rejected alternative, failed attempt, implementation checkpoint, or reason from the previous session. Switching to another coding agent makes that boundary even more obvious.

> **A new chat is a new coworker. The project should not have to start over.**

SKIP therefore treats useful project memory as durable project state outside the conversation.

```text
Session A ─┐
Session B ─┼──→ shared SQLite Core ──→ bounded context ──→ current agent
Agent C   ─┘
```

The goal is not to preserve an AI personality or replay every historical token. The goal is to preserve **project continuity and the causal context behind important decisions** across disposable sessions and interchangeable agents.

### 3. Context dumping

Keeping memory is not enough. Giving every historical record to every session creates a different failure:

> Too little history → the agent forgets why the system exists.
> Too much history → context becomes expensive, noisy, stale, and contradictory.

SKIP stores durable state in the shared Core and uses bounded queries to retrieve only the records relevant to the current goal and stage. If a context pack is incomplete, the agent must expand the named missing information rather than assume it does not exist.

### 4. Stale memory becoming mythology

Retrieved history is context, not automatic truth.

A decision may still explain *why* the project reached its current shape while an old source observation, test result, environment claim, or implementation fact has gone stale. SKIP therefore keeps historical rationale and current evidence distinct.

```text
Historical decisions and failures
              +
      current Core state
              +
 current source / evidence checks
              ↓
       current conclusion
```

A remembered endpoint, source path, PASS result, or implementation claim is not treated as current merely because retrieval succeeded.

### 5. Human attention spent at the wrong layer

If a non-developer has to read every generated design document or every changed source file, the workflow has failed to create useful abstraction.

SKIP keeps detailed evidence and technical relationships available to the agent while reducing human review to decisions, claims, risks, and outcomes that actually need human judgment.

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

## Records are not documentation theater

The current runtime stores business state in one SQLite Core rather than a parallel set of Markdown/YAML workflow files.

Goals, decisions, selections, requirements, plans, work items, evidence, failures, guidance, provenance, and lifecycle state use typed, revision-qualified relationships. Sealed revisions remain history instead of being silently overwritten.

A human-facing review can stay compact:

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

The detailed relationships exist so the next reasoning step — and the next session — can recover what matters without asking the human to operate a documentation system.

**Read the decisions. Skip the implementation details.**

## Long-term project memory

Different record classes answer different questions:

- goal and PRODUCT records: what are we trying to achieve and what did the human decide?
- plan/work relationships: how is that decision intended to become implementation?
- failure and learning records: what went wrong, what was tried, and under what conditions does that lesson apply?
- evidence/current facts: what has actually been observed for the current source and environment?

The Core exposes bounded context for an explicit goal and stage. It does not silently widen an empty or ambiguous result into "read everything".

Fresh sessions should read the current goal context rather than infer state from conversation memory. Historical imports remain historical; retrieving them does not create a new approval, selection, or verification result.

## Approval and authority are not the same as stored text

Publishing a record, retrieving a context pack, attaching a saved request, or receiving a model-written proposal does not create human execution authority.

Current host adapters may bind the actual user turn or native UI action to a request. Material execution then re-checks the exact work, relevant record revisions, policy, risk, source snapshot, and current instruction basis.

This separation matters because a system that preserves memory must not let old memory impersonate a new instruction.

## Cost model

Reducing the agent's token usage is **not SKIP's goal**.

SKIP should still avoid irrelevant context, unnecessary repeated investigation, and wasteful retrieval. Efficiency matters. But token usage is something to optimize, not the objective that defines the workflow.

When additional context is needed to preserve intent, surface decisions, verify repository reality, or carry project memory safely across sessions, SKIP is willing to spend it.

A full workflow may be unnecessary for a tiny reversible change. For permissions, inventory, money, destructive actions, persisted state, migrations, external integrations, concurrency, rollback, and business rules, the additional context can be worth the cost.

> **SKIP uses context as efficiently as it can, but it does not trade away semantic safety just to minimize tokens.**

## Limits

SKIP does **not** increase the underlying agent's physical reasoning capacity, context window, or inherent output quality.

A smaller or weaker model can still make incorrect inferences while following SKIP. The workflow itself also consumes context for investigation, records, decisions, design, and verification, so SKIP can sometimes push an agent closer to its context limit rather than farther away from it.

What it can do is put boundaries around the consequences.

> **The goal is to stop a model limitation before it becomes unverified code or reaches a running service.**

Repository evidence, explicit uncertainty, human decision boundaries, execution checks, and verification exist so questionable reasoning has places to stop before it becomes an authorized implementation or operational change.

SKIP also remains advisory: it does not physically intercept arbitrary writes by the host agent or provide same-OS-user privilege isolation.

## Who this is for

SKIP is especially useful for:

- domain experts building tools for their own work ([QuickHack example](../../examples/quickhack/README.md)),
- operators and analysts automating business processes,
- non-traditional developers working with coding agents,
- solo builders who can define desired behavior more easily than architecture,
- long-running projects where intent, rationale, failures, and evidence need to survive beyond one conversation or one agent.

## Who this is not for

If you can already say:

> Change this object, replace this interface, add this migration, and update these callers.

then SKIP may feel unnecessarily slow for many tasks. Direct coding-agent instructions can be faster for small, self-contained work whose context is already complete.

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
