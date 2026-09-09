# Decision runtime contract

## Boundary

The runtime is goal-scoped and additive. Legacy goals without `features/<goal>/.skip/` remain read-only. Its Markdown artifacts remain human-readable; immutable JSON-compatible YAML events are authority and `projection.yaml` is only a rebuildable cache.

## Commands

- `inbox`: read unresolved gates and decisions.
- `gate`: evaluate `requirements`, `design`, `tasks`, `implement`, `validate`, or `deploy` independently.
- `mutation`: create a side-effect-free preview from `skip-mutation/v1`.
- `allow`: revalidate and commit the exact preview.
- `history`: read a bounded event history.

A mutation may change approval, validation receipt, deploy receipt, or lifecycle only. It must never contain arbitrary source patches.

## Authority

Valid authority kinds are `user_turn`, `native_user_action`, and separately confirmed `interactive_cli`. `agent_proposal`, assistant output, quotations, tool output, and agent-run shell commands cannot approve. Bare `$skip --allow` is valid only when the adapter can prove there is exactly one pending request; otherwise return `NO_PENDING_TARGET` or `AMBIGUOUS_TARGET` with exact callers.

Approval is bound to the request ID, target, action, payload, and artifact digest. Recompute them immediately before commit. A mismatch is `STALE_DIGEST` or `INVALID_AUTHORITY`.

## Lifecycle and gates

Goal lifecycle is `active`, `completed`, `revoked`, or `superseded`. Revocation preserves history and current source facts; it does not delete implementation. Default active routing excludes revoked and superseded goals once the projection-aware selector is enabled.

Gate results are `ALLOW`, `BLOCKED`, `STALE`, or `EVIDENCE_PENDING`. `implement=ALLOW` never implies `deploy=ALLOW`. Deploy requires fresh validation, target and impact, rollout and rollback evidence, plus a separate deploy approval.

The read-only `read_snapshot()` API supplies consistent current gates and approval provenance (event, target/current digest, ledger head) to `prepare`. It retries a changing snapshot once, then returns `SOURCE_CHANGED`. Existing gate CLI fields and verdict rules remain unchanged. Document READY, prepared workflow, and actual authorization are separate states; see [workflow-runtime-contract.md](workflow-runtime-contract.md).

## Capability claims

The canonical engine works everywhere, but its default enforcement label is `advisory`. Use `host-enforced` only after a host adapter's user-origin and write/deploy interception have been independently verified. UI convenience, composer insertion, or a Skill instruction alone is not write enforcement. Apply the evidence matrix in [host-capability-baseline.md](host-capability-baseline.md).

## Storage and recovery

Events use exclusive creation, contiguous sequence numbers, and `previous_event_id`. Writers take a goal-local atomic directory lock, recheck the digest and head, commit the immutable event, and atomically replace the projection. Any ambiguous recovery state fails with `RECOVERY_REQUIRED`; the projection can always be rebuilt from committed events.
