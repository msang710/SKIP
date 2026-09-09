# SKIP

> **Read the decisions. Skip the implementation details.**
>
> You need to know what you are trying to build. You do not need to know where every change belongs.

**SKIP** is a human–AI development workflow for people who understand their problem better than they understand the codebase.

It investigates the repository, separates facts from assumptions, returns product decisions to the human, waits for approval, designs and verifies the implementation, and preserves the project memory that the next conversation or the next agent would otherwise lose.

> **You do not have to read everything SKIP writes. Your agent does.**

The documents are not homework. They are structured memory, evidence, handoff material, and implementation context for the coding agent. Human attention is reserved for the parts that actually require human authority: **intent, product decisions, approval, risk, and verified outcomes.**

The project is a Codex skill **`skip`**, invoked as `$skip`, with a Python CLI for bounded record selection, decision gates, workflow preparation, and reporting.

This repository contains the current development source. Runtime gate enforcement is **`advisory`**; no host write-interception adapter is bundled.

**[English](#english) · [한국어](#한국어)**

---

# English

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

- domain experts building tools for their own work,
- operators and analysts automating business processes,
- non-traditional developers working with coding agents,
- solo builders who can define desired behavior more easily than architecture,
- long-running projects where intent and decisions need to survive beyond one conversation or one agent.

## Who this is not for

If you can already say:

> Change this object, replace this interface, add this migration, and update these callers.

then SKIP may feel unnecessarily slow.

You already possess the implementation-level map that SKIP spends time reconstructing and validating. Direct coding-agent instructions may be faster and cheaper.

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

See the [workflow contract](references/workflow-runtime-contract.md) for request/result schemas, exit codes, source fingerprint coverage and the Python host cache API. `prepare` and `report` do not change source files, record approvals or perform deployment.

### CLI entry points

`$skip` is an agent skill invocation. `./skip` is the terminal entry point. They are different interfaces:

```bash
./skip --project PROJECT                    # Interactive rule setup; requires a TTY
./skip "Investigate the order workflow"     # Emits skip.invoke/v1 for a provider adapter
python3 scripts/intent_context.py --help    # Deterministic backend commands
```

The natural-language terminal form emits a request envelope; it does not start an agent. No global `skip` command is installed by cloning this repository.

## Remaining integration work

Project rules, Context Pack compilation and the workflow preparation layer are implemented. Host-specific record viewers, context attachment UIs, and write/deploy interception belong to separate adapters. A source checkout does not install a Paseo plugin, provide universal IDE integration, or establish `host-enforced` guarantees. No such adapter is shipped here.

### Known development gap

The `history` CLI currently emits its history JSON and then exits with code 2 / `internal_tool_error` because its result does not contain the status field expected by the CLI dispatcher. Do not treat that command as a successful machine-readable history export. The Python history reader and the `prepare` snapshot/provenance path are separate from that dispatcher failure. This issue is not covered by the passing history API tests.

## Verification

The current source was checked on **Linux with Python 3.14.7**. Run the suite from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  scripts.test_intent_context scripts.test_decision_runtime scripts.test_decision_runtime_store \
  scripts.test_workflow_runtime scripts.test_context_session scripts.test_workflow_report
```

The suite contains **93 tests**, including approval reuse/staleness, revoked goals, bounded selection, source changes, report evidence, and cache isolation/corruption/concurrent writes. The original selection/context/gate tests remain in the suite.

In a synthetic four-document fixture, cold parsing handled four documents and a warm call reparsed none while producing the same document Context Pack. Both calls still evaluated current gates and read original hashes. This is not a general speed or token-saving benchmark. Real-host conversation quality, GUI acceptance and pre-write enforcement require separate evidence.

## Install

This is a source checkout for local skill use. It does not install a daemon, a host adapter, or Python packages. The backend uses Python's standard library; the terminal setup UI imports `curses`, and the optional host cache uses POSIX filesystem operations. Linux is the verified environment; native Windows/macOS execution has not been qualified.

Install into the per-user `.agents/skills` directory described in the [official Codex skill documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills). Use an unused destination; cloning does not overwrite an existing skill checkout.

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\.agents\skills" | Out-Null
gh repo clone msang710/SKIP "$HOME\.agents\skills\skip"
```

### macOS / Linux

```bash
mkdir -p "$HOME/.agents/skills"
gh repo clone msang710/SKIP "$HOME/.agents/skills/skip"
```

Authenticate first when needed:

```bash
gh auth login
```

Codex detects skill changes automatically; restart it if the skill does not appear. Existing active sessions may still need a fresh task to use the updated instructions. [Official skill discovery guidance](https://learn.chatgpt.com/docs/build-skills).

## Use

The current skill identifier is `$skip`.

With no arguments it behaves like `--help` and is side-effect free.

```text
Use $skip to investigate this feature, show the plan first, and do not implement before approval.
```

Common context selectors:

```text
$skip --now
$skip --YYMMDD
$skip --date <date>
$skip --goal <goal>
$skip --artifacts <artifact>
$skip --focus decisions
$skip --decision <decision>
$skip --verify
$skip --compare ...
```

Use `$skip --help` for the current option reference.

## Records

The Linux default is `~/.local/share/SKIP` (or `$XDG_DATA_HOME/SKIP`). macOS and Windows defaults and the local project registry are documented in the [record-store contract](references/record-store-contract.md). `--record-root` and `INTENT_TO_CODE_RECORD_ROOT` can select an explicit store.

A record project must already exist for backend commands that resolve it. Use an explicit `--project` with that project's metadata or a registered workspace identity. `--project` does not create or register a project. The repository ships no personal record store.

Historical artifacts are stored under:

```text
<record-root>/projects/<project-id>/features/<goal-slug>/
```

Current-state records live under:

```text
<record-root>/projects/<project-id>/NOW/
```

The record store may contain detailed development history and should be treated as private project data unless deliberately prepared for publication.

A public distribution of SKIP should ship the workflow, retrieval logic, documentation, tests, and synthetic examples — **not the author's real project records.**

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

---

# 한국어

> **결정은 읽고, 구현 세부사항은 SKIP.**
>
> 무엇을 만들고 싶은지는 알아야 합니다. 어디를 어떻게 고쳐야 하는지까지 알 필요는 없습니다.

**SKIP**은 코드베이스보다 자신이 해결하려는 문제를 더 잘 아는 사람을 위한 인간–AI 개발 협업 워크플로입니다.

저장소를 조사하고, 사실과 추측을 분리하고, 숨어 있는 제품 결정을 사람이 답할 수 있는 질문으로 끌어올리고, 승인을 기다린 뒤 설계·구현·검증하고, **새 대화나 다른 에이전트가 잃어버릴 프로젝트 기억을 세션 밖에 보존합니다.**

> **SKIP이 쓰는 모든 문서를 당신이 읽을 필요는 없습니다. 에이전트가 읽습니다.**

문서는 숙제가 아닙니다. 에이전트가 긴 작업과 다음 세션을 이어가기 위한 구조화된 기억이자 근거, 인수인계 자료, 구현 컨텍스트입니다.

사람의 집중력은 정말 사람이 결정해야 하는 것에 사용합니다. **의도, 제품 결정, 승인, 위험, 검증 결과**입니다.

현재 Codex Skill ID는 `skip`이며 `$skip`으로 호출합니다.

## 왜 SKIP을 만들었는가

코딩 에이전트는 이미 많은 사람이 검토할 수 있는 속도보다 빠르게 코드를 작성합니다.

하지만 업무를 정확히 아는 것과 코드 구조를 정확히 아는 것은 다른 능력입니다.

어떤 사람은 이렇게 말할 수 있습니다.

> 예약된 재고는 판매 가능하면 안 된다.
> 주문을 취소하면 예약을 풀어야 한다.
> 단 송장이 이미 발행됐다면 자동으로 풀면 안 된다.

하지만 이렇게 말하지는 못할 수 있습니다.

> `ReservationService`를 바꾸고 migration을 추가하고 두 caller를 수정하고 worker를 idempotent하게 만들어라.

**그것까지 알 필요는 없습니다.**

SKIP은 첫 번째 지식을 보존하고 두 번째 문제를 에이전트에게 맡기기 위해 존재합니다.

```text
사용자는 원하는 결과를 안다
          ↓
SKIP이 현재 구현을 조사한다
          ↓
숨은 제품 결정을 사람에게 돌려준다
          ↓
사용자가 결과를 결정한다
          ↓
에이전트가 설계하고 구현한다
          ↓
결과를 검증한다
          ↓
다음 세션과 다음 에이전트를 위한 기억을 남긴다
```

## 무엇을 SKIP하고, 무엇을 SKIP하면 안 되는가

```text
저장소 고고학                 → SKIP
caller 추적                  → SKIP
구현 세부사항                 → SKIP
기술 설계 문서 대부분          → SKIP
생성된 문서 대부분             → SKIP

내가 원하는 결과               → 절대 SKIP 금지
제품 결정                     → 절대 SKIP 금지
의미 있는 승인                 → 절대 SKIP 금지
알려진 위험과 차단 요소          → 절대 SKIP 금지
검증 결과                     → 절대 SKIP 금지
```

사람을 개발에서 제거하려는 것이 아닙니다.

**사람의 판단이 가장 가치 있는 층으로 사람을 옮기는 것**이 목적입니다.

## 그래도 무엇을 만들지는 알아야 한다

SKIP은 애매한 의도까지 대신 해결하지 않습니다.

> **어떻게 만들지는 몰라도 됩니다. 하지만 무엇을 만들고 싶은지는 알아야 합니다.**

"재고관리 프로그램 만들어줘"만으로는 좋은 시스템을 보장할 수 없습니다.

반면 다음처럼 원하는 세계의 규칙을 설명할 수 있다면 훨씬 멀리 갈 수 있습니다.

> 예약된 재고는 중복 할당되면 안 된다. 실패 원인은 나중에 추적할 수 있어야 한다. 확정된 상태는 권한 있는 작업자만 되돌릴 수 있어야 한다.

코딩 지식보다 **문제 정의와 원하는 결과에 대한 지식**이 중요합니다.

## SKIP이 막으려는 실패

### 1. AI가 빈칸을 조용히 결정하는 것

```text
사람의 의도
    ↓
불완전한 요청
    ↓
AI가 빈칸을 조용히 추측
    ↓
그럴듯한 구현
    ↓
나중에: "왜 이렇게 동작하지?"
```

SKIP은 이를 다음처럼 바꿉니다.

```text
사람의 의도
    ↓
저장소 근거 조사
    ↓
FACT / PRODUCT / DESIGN 분리
    ↓
미해결 PRODUCT 결정은 사람에게 반환
    ↓
승인
    ↓
설계
    ↓
구현
    ↓
검증
```

에이전트는 승인된 결과를 **어떻게 구현할지** 결정할 수 있습니다.

사용자가 **어떤 결과를 받아야 하는지**를 조용히 대신 결정해서는 안 됩니다.

### 2. 새 대화에서 사라지는 기억

AI와 장기 프로젝트를 하다 보면 세션 경계가 곧 인수인계 경계라는 사실이 드러납니다.

같은 모델을 새 대화에서 다시 불러도 이전 세션의 모든 결정, 정정, 실패, 이유, 구현 체크포인트를 자동으로 이어받는 것은 아닙니다. 다른 코딩 에이전트로 바꾸면 그 단절은 더 분명해집니다.

> **새 대화는 새 담당자다. 프로젝트까지 새로 시작할 필요는 없다.**

SKIP은 중요한 프로젝트 기억을 대화창이 아니라 세션 밖의 기록으로 보존합니다.

```text
세션 A ─┐
세션 B ─┼──→ records / decisions / NOW ──→ 필요한 기록 선택 ──→ 현재 에이전트
에이전트 C ─┘
```

목표는 AI의 인격을 보존하는 것이 아닙니다.

**프로젝트의 연속성을 보존하는 것**입니다.

### 3. 모든 기억을 컨텍스트에 붓는 것

기억을 보존하는 것만으로는 부족합니다.

> 과거 기록을 너무 적게 주면 왜 그렇게 만들었는지 잊습니다.
> 전부 주면 컨텍스트가 비싸고 시끄럽고 서로 충돌합니다.

SKIP은 과거 기록을 별도로 보관하고 현재 작업에 필요한 기록만 선택합니다.

### 4. 사람의 집중력을 잘못된 층에 쓰는 것

비개발자가 생성된 설계 문서와 변경된 소스 코드를 전부 읽어야만 안전한 개발이 가능하다면 추상화가 제대로 된 것이 아닙니다.

SKIP은 세부 근거는 에이전트에게 남기고 사람이 실제로 판단해야 하는 결정, 주장, 위험, 결과를 위로 끌어올립니다.

## FACT, PRODUCT, DESIGN

### FACT

현재 시스템이 실제로 어떻게 동작하는가.

소스 코드, 스키마, migration, 테스트, 설정, revision 상태, 실제 실행 결과를 근거로 사용합니다. 검증되지 않은 내용은 `assumption`, `inference`, `gap`, `EVIDENCE_PENDING`으로 남깁니다.

### PRODUCT

사용자나 운영자가 경험하는 결과를 바꾸는 선택입니다.

접근 권한, 상태 전이, 금액과 수량, 재고, 취소와 삭제, 실패와 복구, 호환성과 운영 정책 등이 해당합니다.

이 결정의 최종 권한은 사람에게 있습니다.

### DESIGN

승인된 결과를 어떻게 구현할 것인가.

파일 구조, API, 스키마, 알고리즘, migration, retry, idempotency, concurrency, observability, 테스트, rollout, rollback 등이 여기에 해당합니다.

승인된 사용자 결과를 바꾸지 않는다면 보통 에이전트가 결정합니다.

## 문서는 대부분 에이전트가 읽으라고 쓰는 것이다

전체 워크플로에서는 다음과 같은 문서가 생길 수 있습니다.

```text
impact.md
prd.md
user_stories.md
system_design.md
tasks.md
```

원한다면 전부 읽을 수 있습니다.

보통은 그럴 필요가 없습니다.

이 문서들의 가장 중요한 역할은 다음 추론 단계와 **다음 세션**이 이전 조사와 결정을 잊거나 다시 추측하지 않도록 구조화된 컨텍스트를 제공하는 것입니다.

사람에게 보여주는 검토 내용은 다음처럼 압축될 수 있습니다.

```text
이번에 바뀌는 것
- 예약 재고는 더 이상 출고 가능 수량에 포함되지 않음

결정 필요
- 송장 발행 후 택배사 전송 실패 상태에서는 언제 예약을 풀 것인가?

추천
- 배송이 명시적으로 무효 처리될 때까지 예약 유지

위험
- 너무 일찍 해제하면 중복 할당 가능

검증
- PASS: 재고 배정 / 주문 취소 회귀 테스트
```

**결정은 읽고, 구현 세부사항은 SKIP.**

## 장기 프로젝트 기억

과거 기록은 다음 질문에 답합니다.

> 왜 이런 결정을 했는가?

`NOW`는 다음 질문에 답합니다.

> 지금 실제로 무엇이 구현되어 있는가?

현재 구현은 프로젝트, 날짜, goal, artifact, decision, 현재 상태를 기준으로 bounded selection을 지원합니다.

```text
$skip --now
$skip --260825
$skip --goal stock-allocation
$skip --focus decisions
$skip --setup
```

결과가 없다고 범위를 몰래 넓혀 전체 기록을 읽지 않는 fail-closed 방식입니다.

`--setup`에서는 기본 협업 규칙 10개와 project-specific rule을 확인하고 편집할 수 있습니다. 저장 전 정확한 변경 내용을 먼저 보여주며 사용자의 명시적 승인만 이를 적용할 수 있습니다.

선택 규칙은 모델이 매번 즉흥적으로 재구현하는 것이 아니라 `scripts/intent_context.py`에서 실행 가능한 로직으로 관리합니다.

### `NOW`는 유용하지만 진실은 아니다

`NOW`는 검증된 현재 구현 상태를 압축한 교체 가능한 routing view입니다.

하지만 독립적인 진실로 취급하지 않습니다.

현재 작업에 중요한 주장은 다시 코드, 테스트, 스키마, 설정, 실제 실행 결과와 대조합니다.

```text
과거 기록
   ↓
 NOW
   ↓
필요한 컨텍스트만 선택
   ↓
현재 저장소에서 재검증
```

**기억은 세션을 넘어 살아남아야 하지만, 신화가 되어서는 안 됩니다.**

## 비용

SKIP의 목표는 **에이전트의 토큰 사용량을 줄이는 것이 아닙니다.**

불필요한 컨텍스트, 중복 조사, 낭비되는 탐색은 당연히 줄여야 합니다. 효율화는 중요합니다. 하지만 토큰 사용량은 최적화할 대상이지, SKIP의 워크플로를 정의하는 목표 자체는 아닙니다.

사용자의 의도를 보존하고, 필요한 결정을 끌어올리고, 현재 저장소를 검증하고, 세션 사이에 프로젝트 기억을 안전하게 승계하는 데 추가 컨텍스트가 필요하다면 SKIP은 그 비용을 사용합니다.

작고 되돌리기 쉬운 변경에는 전체 워크플로가 불필요할 수 있습니다. 반면 권한, 재고, 금액, 삭제, 영속 상태, migration, 외부 연동, 동시성, rollback, 업무 규칙 같은 작업에서는 추가 컨텍스트의 비용이 가치 있을 수 있습니다.

> **SKIP은 가능한 한 컨텍스트를 효율적으로 사용하지만, 토큰을 줄이기 위해 의미상의 안전성을 포기하지 않습니다.**

## 한계

SKIP 자체가 **기반 에이전트의 추론 능력, 컨텍스트 창, 결과 품질의 물리적 한계를 뛰어넘게 하지는 않습니다.**

작거나 추론 능력이 부족한 모델은 SKIP을 사용해도 여전히 틀린 추론을 할 수 있습니다. 또한 SKIP은 조사, 기록, 결정, 설계, 검증을 위해 컨텍스트를 사용하므로, 경우에 따라서는 오히려 에이전트를 컨텍스트 한계에 더 가깝게 만들 수도 있습니다.

SKIP은 이런 한계를 없애지 않습니다.

대신 **그 한계의 결과가 검증되지 않은 코드나 운영 중인 서비스에 도달하기 전에 차단하는 것**을 목표로 합니다.

> **모델의 한계가 실제 코드나 운영 변경이 되기 전에 멈추게 한다.**

저장소 근거 확인, 불확실성의 명시, 승인 단계, 검증 절차는 잘못되었을 수 있는 추론이 구현 권한을 얻거나 운영 변경으로 이어지기 전에 멈출 지점을 만들기 위해 존재합니다.

에이전트가 자신의 추론 능력이나 컨텍스트 한계 안에서 충분한 근거를 확보하지 못했다면, 올바른 결과는 자신감을 꾸며내는 것이 아니라 `gap` 또는 `EVIDENCE_PENDING`으로 멈추는 것입니다.

## 누구를 위한 도구인가

특히 다음과 같은 사람에게 잘 맞습니다.

- 자신의 업무 문제를 직접 해결하고 싶은 도메인 전문가,
- 프로세스를 자동화하려는 운영자와 분석가,
- 전통적인 개발자가 아니지만 코딩 에이전트로 소프트웨어를 만드는 사람,
- 아키텍처보다 원하는 동작을 더 정확히 설명할 수 있는 1인 제작자,
- 한 번의 채팅이나 하나의 에이전트를 넘어 프로젝트 기억을 유지해야 하는 사람.

## 누구에게는 맞지 않는가

이미 다음처럼 지시할 수 있다면 SKIP은 느리고 비싸게 느껴질 수 있습니다.

> 이 객체를 바꾸고, 이 인터페이스를 교체하고, migration을 하나 추가하고, 이 caller들을 수정해.

이미 구현 수준의 지도를 가지고 있기 때문입니다. 그 경우에는 코딩 에이전트에게 직접 지시하는 편이 더 빠를 수 있습니다.

## 현재 워크플로

중요한 변경에서는 대략 다음 순서를 따릅니다.

1. 목표, 요청 단계, 범위, 비목표, 프로젝트, 선택된 컨텍스트를 보존합니다.
2. 현재 저장소와 영향을 받는 경로를 조사합니다.
3. 사실, 가정, 공백, 제품 결정, 설계 선택을 분리합니다.
4. 실제 제품 결정을 사용자와 해결합니다.
5. 요구사항과 관찰 가능한 acceptance criteria를 작성합니다.
6. 제품 동작에 대한 명시적 승인을 요청합니다.
7. 구현과 실패/복구 경로를 설계합니다.
8. 저장소 현실을 다시 확인하고 설계 승인을 요청합니다.
9. 승인된 설계에서 실행 가능한 작업을 생성합니다.
10. 승인 범위 안에서만 구현합니다.
11. 변경에 비례한 검증을 수행합니다.
12. 검증된 성공 이후에만 관련 `NOW`를 갱신합니다.

## 현재 구현된 구성 요소

| 구성 요소 | 현재 동작 | 경계 |
|---|---|---|
| Skill | FACT / PRODUCT / DESIGN, 승인 범위를 지키는 계획과 비례하는 검증 | 호스트의 파일 쓰기를 가로채는 기능은 아님 |
| `resolve`, `goals`, `select` | 프로젝트 식별, 제한된 목표 매칭, 기록 필터 | 모호하거나 결과가 없어도 조회 범위를 넓히지 않음 |
| `context` | 단계별 Context Pack, 필요한 추가 읽기와 적용 규칙 | 기록이 현재 실행의 독립적 증거가 되지는 않음 |
| `setup`, `./skip` | 기본 규칙과 사용자가 작성한 프로젝트 규칙; backend의 환경·작업 범위 규칙 | 미리보기와 명시적 적용; 터미널 UI는 TTY 필요 |
| Decision Runtime | 목표별 ledger, 승인 digest, inbox, lifecycle, 동작별 gate | legacy 자동 초기화 없음; 구현 허용과 배포 허용은 별개 |
| `prepare` | 요청 깊이, 선택 문서, 현재 권한·소스 상태와 다음 행동 | 읽기 전용 조정이며 prepared는 실행 권한이나 완료가 아님 |
| `report` | 근거가 연결된 결과를 brief/detail/JSON으로 표현 | 제출된 근거를 표시하며 검증 명령을 직접 실행하지 않음 |
| 세션 캐시 | 호스트가 수명을 관리하는 선택적 문서 파싱 캐시 | 승인·대화·소스 검증·실행 근거는 저장하지 않음; 일반 CLI는 uncached |

작업 깊이는 `answer / compact / full`로 나누고 실행 권한과 분리합니다. 같은 범위와 현재 digest의 유효한 승인은 재사용하며, 변경된 문서를 모델의 의미 동등성 판단으로 자동 승인하지 않습니다. 계획 요청을 구현으로 확대하지 않습니다.

### CLI 진입점

`$skip`은 에이전트 Skill 호출이고 `./skip`은 터미널 실행 파일입니다.

```bash
./skip --project PROJECT                    # 규칙 설정 UI; TTY 필요
./skip "주문 흐름을 조사해"                   # provider adapter용 skip.invoke/v1 출력
python3 scripts/intent_context.py --help    # 결정적 backend 명령 목록
```

터미널의 자연어 호출은 요청 envelope를 출력하며 에이전트를 직접 실행하지 않습니다. 저장소를 clone해도 전역 `skip` 명령이 자동 설치되지는 않습니다.

## 남은 연동 범위

프로젝트 규칙, Context Pack, workflow prepare는 구현되어 있습니다. 호스트별 기록 뷰어·현재 세션 첨부 UI·쓰기 및 배포 차단은 별도 adapter의 책임입니다. 이 저장소에는 Paseo 플러그인이나 범용 IDE 연동 adapter가 포함되어 있지 않으며, 현재 강제력 표시는 `advisory`입니다.

### 알려진 개발본 한계

현재 `history` CLI는 history JSON을 출력한 뒤 종료 코드 2와 `internal_tool_error`를 반환합니다. 결과에 CLI dispatcher가 기대하는 status 필드가 없기 때문입니다. 성공한 기계 처리용 history export로 취급하면 안 됩니다. Python history reader와 `prepare`의 snapshot/provenance 경로는 이 dispatcher 오류와 별개이며, 통과한 history API 테스트가 CLI 성공까지 보장하지는 않습니다.

## 검증

현재 소스는 **Linux / Python 3.14.7**에서 검증했습니다. 저장소 루트에서 실행합니다.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  scripts.test_intent_context scripts.test_decision_runtime scripts.test_decision_runtime_store \
  scripts.test_workflow_runtime scripts.test_context_session scripts.test_workflow_report
```

전체 **93개 테스트**는 기존 selector/context/gate 회귀와 승인 재사용·만료·철회, 소스 변경, 보고 근거, 캐시 격리·손상·동시 쓰기를 포함합니다.

문서 4개를 사용하는 synthetic fixture에서는 cold 본문 파싱 4회, warm 재파싱 0회에 같은 문서 Context Pack을 반환했습니다. 두 호출 모두 현재 gate와 원본 해시를 다시 확인했습니다. 일반적인 속도·토큰 절감률을 입증한 것은 아니며, 실제 호스트 대화 품질·GUI·쓰기 차단은 별도로 검증해야 합니다.

## 설치

로컬 Skill 사용을 위한 소스 checkout입니다. daemon·호스트 adapter·Python 패키지를 설치하지 않습니다. backend는 Python 표준 라이브러리를 사용하고, 터미널 UI는 `curses`, 선택적 호스트 캐시는 POSIX 파일시스템 기능을 사용합니다. Linux에서 검증했으며 네이티브 Windows/macOS 실행은 검증하지 않았습니다.

[공식 Codex Skill 문서](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)의 사용자별 `.agents/skills` 경로에 설치합니다. 이미 설치된 경로를 덮어쓰는 명령은 아니므로 비어 있는 목적지를 사용합니다.

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\.agents\skills" | Out-Null
gh repo clone msang710/SKIP "$HOME\.agents\skills\skip"
```

### macOS / Linux

```bash
mkdir -p "$HOME/.agents/skills"
gh repo clone msang710/SKIP "$HOME/.agents/skills/skip"
```

필요하면 먼저 GitHub CLI를 인증합니다.

```bash
gh auth login
```

Codex는 Skill 변경을 자동 감지합니다. 나타나지 않으면 재시작하고, 기존 작업이 이전 지침을 사용 중이면 새 작업에서 확인합니다. [공식 안내](https://learn.chatgpt.com/docs/build-skills).

## 사용

현재 Skill ID는 `$skip`입니다.

인자 없이 호출하면 `--help`와 동일하게 동작하며 부작용이 없습니다.

```text
$skip으로 이 기능을 조사하고, 계획을 먼저 보여준 뒤 승인 전에는 구현하지 마.
```

주요 컨텍스트 선택 옵션:

```text
$skip --now
$skip --YYMMDD
$skip --date <date>
$skip --goal <goal>
$skip --artifacts <artifact>
$skip --focus decisions
$skip --decision <decision>
$skip --verify
$skip --compare ...
$skip --setup
```

현재 옵션은 `$skip --help`에서 확인할 수 있습니다.

## 기록

Linux 기본 경로는 `~/.local/share/SKIP`이며 `$XDG_DATA_HOME`이 있으면 그 아래의 `SKIP`을 사용합니다. macOS/Windows 기본값과 로컬 프로젝트 registry는 [record-store contract](references/record-store-contract.md)에 정의되어 있습니다. `--record-root` 또는 `INTENT_TO_CODE_RECORD_ROOT`로 저장소를 명시할 수 있습니다.

프로젝트를 조회하는 backend 명령에는 기존 기록 프로젝트가 필요합니다. 해당 메타데이터가 있는 `--project`를 지정하거나 workspace identity를 등록해야 합니다. `--project` 자체는 프로젝트를 생성·등록하지 않으며, 이 소스에는 개인 기록 저장소가 포함되어 있지 않습니다.

과거 산출물은 다음 구조에 저장합니다.

```text
<record-root>/projects/<project-id>/features/<goal-slug>/
```

현재 상태 기록은 다음 위치에 둡니다.

```text
<record-root>/projects/<project-id>/NOW/
```

Record store에는 실제 개발 이력이 세밀하게 남을 수 있으므로, 공개를 목적으로 따로 준비하지 않았다면 **개인 프로젝트 데이터로 취급해야 합니다.**

SKIP의 공개 배포판에는 workflow, retrieval logic, 문서, 테스트, synthetic example을 포함할 수 있지만 **작성자의 실제 `records/`는 포함하지 않는 것**을 원칙으로 합니다.

## Workflow prepare와 결과 보고

개발 CLI의 `prepare`는 선택된 문서, 현재 승인 상태와 다음 행동을 묶어 반환합니다. `answer / compact / full`은 작업 깊이이며 구현 권한을 대신하지 않습니다. 기존 `skip` 설정 TUI는 그대로 유지합니다.

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

`status=prepared`는 조정 결과를 만들었다는 뜻입니다. `document_readiness`와 `authorization.status`를 따로 확인해야 합니다. 승인이나 소스 근거가 없으면 구현 행동을 제안하지 않으며, 기존 기록을 자동 승인하거나 초기화하지 않습니다. 실제 파일 쓰기와 배포는 실행하지 않습니다.

`report --result-file FILE --format brief|detail|json`은 `workflow-result/v1`로 전달한 검증 근거를 표시합니다. 기본 보고는 결과·확인·남은 일이며 관련 실패, 미검증, 차단 상태를 보존합니다. 보고기는 근거에 적힌 테스트를 직접 실행하지 않습니다.

일반 CLI는 캐시 없이 동작합니다. Python 호스트가 세션 종료 시 삭제할 private 저장소를 제공한 경우에만 문서 파싱 캐시를 사용할 수 있습니다. 승인 상태와 소스·실행 검증은 캐시하지 않습니다. 호스트 쓰기 차단 어댑터는 포함하지 않으며 강제력은 `advisory`입니다.

입력·반환 스키마, 소스 fingerprint의 검증 범위와 호스트 캐시 계약은 [workflow-runtime-contract](references/workflow-runtime-contract.md)를 참고하세요.

## 철학

코딩 에이전트의 발전으로 코드 작성 자체의 희소성은 점점 줄어들고 있습니다.

그렇다고 제품 판단, 도메인 지식, 명확한 의도의 가치가 줄어드는 것은 아닙니다. 오히려 더 중요해집니다.

이제 어려운 문제는 단순히 이것만이 아닙니다.

> **AI가 코드를 작성할 수 있는가?**

점점 더 중요한 문제는 이것입니다.

> **불완전한 요청이 검증된 구현이 될 때까지 사람의 원래 의도가 살아남을 수 있는가? 그리고 다음 대화에서도 살아남을 수 있는가?**

SKIP은 그 문제를 위해 만들어졌습니다.

> **코드는 SKIP. 문서 대부분도 SKIP. 구현 세부사항도 SKIP.**
> **의도는 절대 SKIP하지 않는다. 기억도 잃어버리지 않는다.**
