# Workflow preparation and reporting

## Responsibility

`scripts/intent_context.py prepare` returns a read-only `workflow-plan/v1`. It uses the canonical project/goal selector, document compiler, and current Decision Runtime. It does not approve, initialize a goal, execute source changes, deploy, or refresh NOW. `prepared` means a usable coordination result, not permission or task completion.

Use `answer / compact / full` to select workflow depth. Depth never supplies authority. An existing approval may be reused only for its current target/digest and scope; a plan-only request remains a plan even when implementation is allowed. Missing source evidence or unknown impact requires inspection. Legacy goals remain on the explicit human approval workflow; document `approved` does not become a synthetic runtime `ALLOW`.

## Request

```text
python3 scripts/intent_context.py prepare --project PROJECT --goal GOAL --stage design --request-file -
```

Supply JSON through stdin (or a file):

```json
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
```

- `requested_operation`: `answer`, `plan`, `implement`, `validate`, `deploy`.
- Valid stages: answer → restore/impact; plan → impact/requirements/design/tasks; implement → implementation; validate/deploy → validation.
- `requested_depth`: auto/answer/compact/full. `answer` cannot accompany another operation. Risk or missing scope evidence prevents compact classification.
- `scope.behavior_change`: yes/no/unknown. `risk_flags`: permissions/persisted_data/money/state_transition/integration/destructive/difficult_rollback/unknown. Every flag must be explicit; evidence paths alone do not prove absence of risk.
- `scope.evidence_refs`: source file paths relative to the supplied workspace. Absolute paths, `..`, and symlink escape are rejected. These paths are observations to recheck, not instructions to execute.
- Optional `query` is passed to canonical goal resolution only when `--goal` is absent. It is neither echoed nor persisted. Ambiguous/no-match never widens selection. Conversation continuity is supplied by explicit goal, never inferred from cache.
- Optional `records_required: false` is valid only for a self-contained answer with no record filters. It avoids project, record, source, and cache access.
- Optional `source_evidence: {"snapshot_digest": "..."}` binds the caller's source inspection to a current fingerprint. Inspect the relevant sources before submitting it. Matching the digest verifies bytes and observed Git state only; it does not certify semantic scope, tests, runtime, or GUI behavior.
- Authority and host session fields are not accepted in this JSON. Unknown fields fail validation.

The source snapshot hashes referenced file bytes and Git HEAD/status/diff when available. Uncommitted tracked changes and untracked path additions affect the snapshot; untracked content outside the referenced paths is not covered. Non-Git workspaces are limited to referenced files. The returned coverage and `semantic_scope_verified=false` keep these limits visible.

## Plan and state precedence

The plan contains selection manifest, document readiness, authorization with current reasons/provenance, document Context Pack, required expansions, source snapshot/verification, next action, user decision, warnings, and measurements. The plan's `authorization` is the current execution status; its document-only `context_pack` intentionally contains no cached runtime gates or inbox.

`document_readiness=READY` and `authorization.status=BLOCKED` can coexist. Show their meanings separately. Gate provenance identifies approval event, target digest, current digest and ledger head. Recheck before acting; the result is advisory, not a durable execution token. Newly discovered scope/premise changes must be investigated and reflected in the appropriate artifact before re-evaluation.

Priority: invalid input or authoritative source/ledger failure → stop; unresolved goal → clarify within returned bounds; missing compiled context → expand only selected fields; answer/plan → remain read-only; stale or blocked authority → revise/verify/request the named approval; current authority plus current source → suggest the requested implementation/validation. The first release never dispatches deployment, even if its gate allows it.

`next_action` is answer/inspect_source/expand_context/clarify_goal/present_plan/revise_artifact/request_approval/implement/verify/stop. A `present_plan` result may be a conspicuously marked downstream draft; it does not override the approval order. Do not ask again for an already valid scope/digest approval. A stale document requires approval of that current document; do not transfer authority based on claimed semantic equivalence.

Exit 0: prepared (possibly with blocked execution). Exit 2: invalid/error/incomplete/ambiguous. Exit 3: no_match. Existing select/context/gate exit codes are unchanged. Read both status and authorization. `--help` exits before project, input-file, or record access.

## Session cache

The CLI runs uncached. A host may call `prepare_workflow(args, request, session=SessionContext(...))` from Python. The session object is supplied outside agent JSON, with a private directory, opaque session ID, and a host guarantee to remove the directory at session end. No host adapter is installed by this feature. Without that lifecycle capability, use no session.

The host creates the directory with mode 0700; cache files are 0600. Symlink roots/files and nonprivate ownership/modes are rejected or cause uncached fallback. Unique temporary files and atomic replacement support concurrent writers. The cache stores allowlisted document parse fragments only. It never stores conversation input, source verification, authority envelopes, approval receipts, runtime gates/inbox/lifecycle, or completion status.

Keys include compiler version/content, session, canonical root/project/workspace bindings, goal, selection filters/list, stage, rules/environment/operation and context budget; each fragment also binds its original content hash. Every invocation reselects and hashes originals. Unchanged documents skip semantic parsing; a changed document is reparsed. Current runtime and source checks always run. Cache faults fall back to the same selected source; authoritative failures do not. Snapshot changes are retried once and then reported as an error/incomplete result.

Metrics distinguish parsed documents and cache hits from source file reads and current gate evaluations. A cache hit is not source freshness or authorization. There is no persistent cache registry, last-goal pointer, daemon, telemetry or new database.

## Reports

```text
python3 scripts/intent_context.py report --result-file - --format brief
```

`workflow-result/v1` requires `requested_outcome` (string), `outcome_status` (complete/partial/blocked/not_run), `changes` (string list), `evidence` (list), `authorization` (status/reasons), `gaps` (string list), and `next_decision` (string/null). Optional selection, document_readiness and metrics are retained in detail/json. Formats: brief (default), detail, json.

Each evidence item has surface (source/test/build/package/install/runtime/gui/device/production), status (PASS/FAIL/NOT_RUN/EVIDENCE_PENDING/STALE/BLOCKED), optional reference and summary. PASS without a nonempty reference is downgraded to EVIDENCE_PENDING. The renderer never opens or verifies references itself. An empty evidence set or any unresolved evidence/gap prevents a complete outcome. Report only evidence relevant to the requested outcome and describe excluded deployment separately as needed.

Default output is result / checks / remaining work in the conversation language (the bundled CLI brief labels are Korean). Keep relevant failed/unrun/stale/blocked/unverified states and selection warnings visible. Detail/json retains the full supplied audit data. Never submit a prepare result as a completion report, treat ALLOW as proof of completion, or collapse source/test/install/runtime/GUI evidence into a single PASS.
