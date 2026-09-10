# Minimal entry and adaptive execution

This contract is additive. `workflow-plan/v2` and `execution-gate/v2` never replace or impersonate v1 artifact approval gates. All gates are advisory; SKIP does not intercept host writes.

## First use

The user invokes `$skip <request>` in the existing agent. The agent uses its installed skill directory, not a path in the product repository. Windows packages contain CPython and the same Core; use the executable and argument array in `package-manifest.json`, or the packaged `skip.cmd` for CLI diagnostics. No user Python, Git, npm, pip, WSL, or daemon setup is required by that package. Public catalog placement and actual Windows app installation are separate acceptance evidence; a generated ZIP does not prove them.

`intent_context.py entry` inspects a project without writing. It respects the existing record-root/registry environment variables and platform defaults. A missing project produces a bootstrap preview, not a goal. Native activation binds identity and optionally writes measured file evidence to `NOW/system.md`. It does not generate PRD, design, tasks, goal.json, decisions, or approvals. Directory names and agent memory are not identity or goal authority.

`project.yaml` and the machine registry are control metadata. Existing registry mappings are preserved semantically when written as JSON-compatible YAML. Bootstrap uses an OS process lock, a compare-and-swap registry revision, and a recoverable journal under `<record-root>/.control/bootstrap`. The two locations are not claimed to be one atomic filesystem transaction. An incomplete project has `.bootstrap-pending` and cannot be selected. Retry activation for recovery; changed user files or conflicting identity remain an explicit error. Never delete user data to recover a bootstrap.

NOW is the minimum business record, not a mandatory set of empty files. Write only measured current facts and attributed evidence. The layout in `now-contract.md` is an available structure; create individual files only when useful. Future plans, historical goals inferred from code, and approvals do not belong in NOW.

## Actual user origin

`entry --request-file` accepts work data only. It cannot establish user origin, even if a JSON author labels itself `user_turn`. `UserEvent` is a separate adapter input.

- Codex local adapter: `scripts/codex_entry.py` uses the host's `CODEX_THREAD_ID` and the selected file under its own sessions root. It validates session identity/workspace and the latest actual user-role message ID/body. It reads a bounded tail (16 MiB), never an agent summary or unrelated threads. No per-request transcript or authority file is persisted. Missing/changed formats, ambiguous files, host-context envelopes, unsupported message content, and ambiguous operation wording fail closed or stay read-only. Its conservative operation recognizer supports explicit English/Korean work requests. A continuation can reuse the original request and ephemeral receipt only after revalidating that exact user reference and all intervening user messages in the same live thread. A cancel or changed instruction stops reuse. A bare “yes” without that reference does not invent implementation scope. The actual current Codex host was checked on Linux; Windows app acceptance remains separate.
- Paseo: the selected daemon resolves the real workspace through `paseo.workspaces.ref(id).refresh()`. A native form submission establishes the original request. The server keeps it in process memory for at most 30 minutes. `skip.workflow.prepare` accepts scope/risk/decision updates for that job, never replacement user text, operation, host path, or identity. Cancellation, a host/workspace change, expiry, or process restart invalidates the job.
- Terminal: `entry --interactive` receives a new actual request from a TTY. `entry --activate` is a separate interactive activation. Piped text is not an interactive authority source.

`native_entry.py` is an internal trusted-adapter control channel. An agent must **not** call it to manufacture a native action from its own JSON. The bridge does not authenticate arbitrary same-user OS processes; the native adapter is responsible for provenance. These are advisory integration checks, not a security boundary against a process that can change the host, its session records, or SKIP.

## Scope and risk

A v2 request contains `request_id`, actual `text`, `operation`, `scope: {paths, summary}`, and `open_decisions`, with optional `goal`, `goal_risk`, `change_risk`, and `force_full`. Scope paths are bounded workspace-relative file paths. The Core measures referenced files, including non-existence for a new file. It does not require Git or scan the entire repository.

`goal-risk/v1` records revision, affected failure dimensions, failure impact, reversibility, uncertainty and evidence. `change-risk/v1` binds the goal revision, source digest, scope digest, policy version, actual change dimensions, reversibility, uncertainty, evidence and exclusions. These are execution contracts, not required additional record files. Current implemented risk context may be retained in NOW after source verification; proposed change risk stays in the current work context or required design artifacts.

The agent investigates domain meaning. Hashes prove which files were observed, not that an exclusion is semantically correct. A goal-level risk can be excluded only with a current evidence reference explaining why this change does not reach that risk. Missing/stale evidence or unknown impact leads to investigation, not a low-risk default. Project names never determine procedure.

- `answer`: read-only answer.
- `investigate`: missing, stale or uncertain evidence; inspect current scope first.
- `compact`: bounded, easily reversible, no material impact dimensions; no extra artifact bundle.
- `full`: business rules, inventory, money, permissions, sensitive/persisted data, external state, boot/recovery or hard rollback. Existing artifact-backed goals retain full v1 gates.

Procedure, open product decisions and execution authority are distinct outputs. Compact requires the actual direct implementation request, active goal, no hold/open decisions, current scope/source/risk/policy and the same host/session. Full delegates to the existing runtime gate. Read/plan/activation never implies implement; implement never implies deploy. Deployment is not dispatched.

A receipt is ephemeral and must be compared to a freshly prepared gate immediately before a write. Source changes lead to investigation. Scope expansion, changed risk, revoked goals, holds or new decisions cannot reuse an old receipt. Do not copy an old `ALLOW` from status or attachment text.

## Result and status

`status-view/v1` exposes goal, outcome, decision needed, recommendation, risk summary, checks, gaps, next action and detail references. Preparation is not completion. Result reporting validates `workflow-result/v1`, preserves each evidence surface, downgrades unsupported complete/PASS claims, and checks the after-source snapshot. It does not execute or certify caller-supplied tests.

Paseo RPCs: `skip.workflow.inspect`, `activate`, `start`, `prepare`, `report`, `status`, `cancel`. A `prepare` assessment cannot replace the original event. `report` uses the previously established execution basis, checks the current source and can write only the goal's NOW through revision CAS. `status` rechecks Core state; it is not cached approval. Multi-source NOW requires the actual verified source ID. An unsupported host capability is shown explicitly; fallback must not disguise untested app installation as a success.
