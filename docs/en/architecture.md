# Architecture and runtime

[SKIP](../../README.en.md) · [Concepts and decisions](concepts.md) · [Installation and usage](usage.md) · [Paseo plugin](paseo.md) · [Verification and limits](verification.md)

## Current workflow

For material changes, the current skill follows this general path:

1. Preserve the goal, requested stage, scope, non-goals, project identity, and selected context.
2. Inspect current repository behavior and affected paths.
3. Separate facts, assumptions, gaps, product decisions, and design choices.
4. Resolve genuine product decisions with the user.
5. Draft requirements and observable acceptance criteria.
6. Request explicit product approval.
7. Design the implementation and relevant failure/recovery behavior.
8. Re-check repository reality and request design approval.
9. Create executable tasks from approved design.
10. Implement only within the approved scope.
11. Run proportionate verification.
12. Refresh affected `NOW` state only after verified success.

Narrow, reversible changes may use a compact flow.

## Implemented components

| Component | Current behavior | Boundary |
|---|---|---|
| Skill | FACT / PRODUCT / DESIGN, approval-aware planning and proportional verification | Instructions guide the agent; they do not intercept host writes |
| `resolve`, `goals`, `select` | Project identity, bounded deterministic goal matching, record filters | No automatic widening on ambiguity or no match |
| `context` | Stage-specific Context Pack with required expansions and effective rules | Records are routing context, not independent proof of live behavior |
| `setup` and `./skip` | Core rule toggles and user-authored project rules, including scoped rules in the backend | Explicit preview/apply; terminal UI needs a TTY |
| Decision Runtime | Goal-local ledger, approval digests, inbox, lifecycle, independent action gates | Legacy goals are not auto-initialized; `implement=ALLOW` does not allow deployment |
| `prepare` | Request depth, selected document context, current authorization, source snapshot and next action | Read-only coordination; `prepared` is not permission or completion |
| `report` | `workflow-result/v1` as brief/detail/JSON, preserving unresolved evidence | Supplied evidence is rendered, not executed or independently verified |
| Session cache | Optional host-owned cache of document parsing fragments | No cached authority, conversation, source verification or runtime evidence; ordinary CLI is uncached |
| Paseo plugin | SKIP Records panel, invocation/record attachment sources, exact-record attachment and Decision Inbox | Source in `plugins/paseo`; requires a separately configured Paseo daemon; no write interception |

### Workflow preparation and reports

Run from this repository. Replace `PROJECT` and `GOAL` with an existing external record project and goal:

```bash
python3 scripts/intent_context.py prepare --project PROJECT --goal GOAL \
  --stage design --request-file - <<'JSON'
{
  "schema": "workflow-request/v1",
  "requested_operation": "plan",
  "requested_depth": "auto",
  "scope": {
    "behavior_change": "unknown",
    "risk_flags": ["unknown"],
    "evidence_refs": []
  }
}
JSON
```

A plan request stays a plan. `answer / compact / full` controls workflow depth, while current gates and source checks control the suggested action. An unchanged valid approval is reused; a stale target digest is not treated as equivalent by the model. `document_readiness=READY` may coexist with `authorization.status=BLOCKED`.

```bash
python3 scripts/intent_context.py report --result-file - --format brief <<'JSON'
{
  "schema": "workflow-result/v1",
  "requested_outcome": "Inspect a proposed change",
  "outcome_status": "not_run",
  "changes": [],
  "evidence": [{"surface": "source", "status": "NOT_RUN"}],
  "authorization": {"status": "NOT_REQUIRED", "reasons": []},
  "gaps": ["Source inspection has not run"],
  "next_decision": null
}
JSON
```

The default summary presents the result, checks and remaining work. The bundled CLI labels are Korean; agent responses follow the conversation language. Relevant `FAIL`, `NOT_RUN`, `STALE`, `BLOCKED` and `EVIDENCE_PENDING` stay visible. Full selection and provenance are available in structured/detail output.

See the [workflow contract](../../references/workflow-runtime-contract.md) for request/result schemas, exit codes, source fingerprint coverage and the Python host cache API. `prepare` and `report` do not change source files, record approvals or perform deployment.

### CLI entry points

`$skip` is an agent skill invocation. `./skip` is the terminal entry point. They are different interfaces:

```bash
./skip --project PROJECT                    # Interactive rule setup; requires a TTY
./skip "Investigate the order workflow"     # Emits skip.invoke/v1 for a provider adapter
python3 scripts/intent_context.py --help    # Deterministic backend commands
```

The natural-language terminal form emits a request envelope; it does not start an agent. No global `skip` command is installed by cloning this repository.

## Remaining integration work

Project rules, Context Pack compilation, workflow preparation, and the Paseo plugin source are included. Cloning this repository does not install or reload that plugin. Other IDE adapters, `prepare/report` integration into the plugin UI, and host write/deploy interception remain separate work. No `host-enforced` adapter is bundled.
