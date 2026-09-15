# 구조와 런타임

[SKIP](../../README.md) · [철학과 제품 결정](concepts.md) · [설치와 사용](usage.md) · [Paseo 플러그인](paseo.md) · [검증과 한계](verification.md)

## 현재 워크플로

중요한 변경에서는 대략 다음 순서를 따릅니다.

1. 호스트가 지원하면 실제 현재 사용자 요청과 검증된 origin을 캡처합니다.
2. 저장소 상태나 대화 기억으로 목표를 만들어내지 않고 정확한 목표를 식별하거나 생성합니다.
3. 해당 목표의 fresh bounded context를 읽습니다.
4. 현재 저장소 동작과 영향을 받는 경로를 조사합니다.
5. 사실, 가정, 공백, 제품 결정, 설계 선택을 분리합니다.
6. 실제 PRODUCT 결정을 사용자와 해결합니다.
7. 요구사항과 관찰 가능한 acceptance criteria를 작성합니다.
8. 구현과 관련 실패/복구 동작을 설계합니다.
9. 정확한 requirement/plan/decision revision에 연결된 실행 가능한 work item을 만듭니다.
10. 현재 호스트의 검증된 authority 경로를 통해서만 중요한 실행을 시작합니다.
11. 변경에 비례한 검증을 수행하고 정확한 source/work 참조에 근거를 기록합니다.
12. FAIL, NOT_RUN, STALE, BLOCKED, 불완전 컨텍스트와 미해결 공백을 보존하면서 결과 / 확인 / 남은 일을 보고합니다.

좁고 되돌리기 쉬운 변경은 compact flow를 사용할 수 있습니다. 중요한 업무 규칙, 권한, 재고, 금액, 영속 데이터, 복구, 외부 상태 변경에는 그 위험에 비례한 설계와 검증이 필요합니다.

## 런타임 모델

| 구성 요소 | 현재 동작 | 경계 |
|---|---|---|
| **Skill 지침** | FACT / PRODUCT / DESIGN 분리, 연속성 규칙, 비례하는 workflow와 보고 | 지침은 에이전트를 안내하지만 호스트 쓰기를 물리적으로 가로채지 않음 |
| **공통 SQLite Core** | 업무 기록, revision, 관계, provenance, authority 상태, 근거의 단일 source of truth | 병렬 Markdown/JSON/YAML runtime 업무 저장소 없음 |
| **Typed immutable revisions** | 목표·결정·요구사항·계획·작업이 정확한 revision-qualified 관계 사용 | record publish/seal 자체는 인간 승인 아님 |
| **Bounded context queries** | 명시적 budget 안에서 goal/stage별 기록, 선택, 실패, guidance, 현재 사실 조회 | 불완전 pack을 완전한 지식으로 취급하면 안 됨 |
| **Entry / provenance** | native adapter가 실제 현재 호스트 발화를 input/request/interpretation에 연결 | 지원되지 않는 호스트는 읽고 제안할 수 있지만 verified user provenance를 만들어낼 수 없음 |
| **Execution authority** | 실행 전 현재 요청, source snapshot, policy, risk, 정확한 record revision 재확인 | planning approval은 구현이나 배포 승인을 뜻하지 않음 |
| **Evidence / assurance** | PASS/FAIL/NOT_RUN, 환경·boundary 근거, failure attempt, guidance, assurance obligation 기록 | agent_report를 host observation으로 승격하지 않음 |
| **MCP** | 같은 Core를 읽기/쓰기/query 도구와 decision UI resource로 노출 | 일반 MCP 접근은 인간 승인이나 verified user turn을 인증하지 않음 |
| **Native adapter / UI** | Codex와 Paseo 통합이 현재 host/session/UI context를 Core에 연결 | live host/workspace/agent/thread handle은 ephemeral이며 adapter가 소유 |

## 세션과 에이전트를 넘는 연속성

SKIP은 대화를 장기 저장소가 아니라 버려질 수 있는 작업 컨텍스트로 봅니다.

```text
세션 A ─┐
세션 B ─┼──→ 공통 SQLite Core ──→ bounded context ──→ 현재 에이전트
에이전트 C ─┘
```

새 세션이 소스 코드만 보고 안전하게 재구성할 수 없는 정보 — 제품 의도, 결정 근거, 선택한 옵션, 요구사항, 거부·대체된 기록, 계획, 작업, 실패, 근거, 미해결 공백 — 를 durable record로 보존합니다.

목표는 과거 토큰을 전부 재생하는 것이 아닙니다. Context query는 현재 goal/stage에 관련된 기록만 선택하고, 필요한 정보가 생략된 incomplete 결과는 명시적으로 확장합니다.

과거 컨텍스트도 live truth로 보지 않습니다. 과거 결정은 여전히 이유를 설명할 수 있지만 오래된 저장소 관찰은 stale할 수 있습니다. 필요한 경우 현재 source, selection, policy, evidence, execution basis를 다시 확인합니다.

## Entry, 해석, 권한

사용자의 문장, 저장된 요청, 선택된 record, 실행 authorization은 서로 다른 것입니다.

Native entry는 업무 기록을 만들기 전에 실제 host input을 캡처합니다. 에이전트는 정확한 instruction span과 target에 연결된 structured interpretation을 제안할 수 있지만 parser suggestion이나 agent가 만든 JSON은 인간 권한을 만들지 못합니다.

```text
실제 host input
      ↓
verified input envelope
      ↓
agent interpretation
      ↓
goal / records / work
      ↓
현재 execution checks
      ↓
중요한 action
```

Record를 읽거나 composer에 붙이는 것은 컨텍스트일 뿐입니다. 계획 요청은 계획으로 남습니다. 이후 구현 요청이 이미 준비된 작업을 허용할 수 있지만 execution path는 과거 기록을 고쳐 권한을 만들어내는 대신 정확한 work/source/policy 상태를 다시 확인합니다.

Unknown delivery는 다른 세션에 자동 재전송하지 않습니다. 계획과 durable record는 이식 가능하지만 live routing handle은 그렇지 않습니다.

## Core query와 진입점

일반 에이전트 사용에서는 연결된 MCP 도구를 우선합니다. 대표 도구:

```text
skip_status
skip_context
skip_decisions
skip_submit
skip_amend
skip_result
skip_learning
skip_execution_status
```

설치된 local launcher는 같은 Core를 조회합니다.

```bash
skip --workspace <project-root> query status
```

소스 개발 fallback은 module CLI입니다.

```bash
python -m skip_core.cli --project <project-id> query context --input '{"goal_id":"<goal-id>"}'
```

Codex native adapter는 가능한 경우 현재 발화 provenance와 current execution entry를 제공합니다.

```bash
python -m adapters.codex.entry --workspace <project-root> --project <project-id> --goal <goal-id>
```

배포 이후 퇴역한 `scripts/intent_context.py`나 파일 기반 runtime writer를 사용하지 마세요. 권위 있는 현재 명령과 schema 동작은 [Core 계약](../../references/db-core-contract.md)에 있습니다.

## 저장과 revision 모델

SQLite가 유일한 runtime 업무 기록 저장소입니다. Core는 immutable/sealed revision, 정확한 foreign-key 관계, transaction command, CAS/idempotency, bounded query, 명시적 schema upgrade를 사용합니다.

Decision, requirement, plan, source basis, policy가 바뀌면 이전 revision의 authority를 조용히 이어받지 않습니다. Current projection은 record 순서에서 모델이 추측하게 하지 않고 selection과 staleness를 명시적으로 노출합니다.

이관된 historical record는 원본 text와 관계를 보존할 수 있지만 과거 status가 현재 승인이나 검증이 되지는 않습니다. 예전 file runtime 자료는 recovery/regression provenance일 뿐 두 번째 live writer가 아닙니다.

## 실패 학습과 검증

일반 FAIL도 근거로 남습니다. 중요한 실패는 typed failure/attempt record와 이후 guidance로 이어질 수 있습니다. Assurance query는 관련 environment, scenario, obligation, evidence, exception을 연결해 한 boundary의 PASS가 다른 boundary까지 자동 일반화되지 않게 합니다.

의도적으로 구분하는 예:

- unit/integration test vs packaged runtime
- mock DB vs 실제 database competition
- VM vs physical hardware
- agent report vs host observation
- implementation completion vs deployment acceptance

따라서 현재 source 검증도 연속성의 일부입니다. Memory는 프로젝트가 왜 이 상태에 도달했는지 설명할 수 있지만, memory만으로 그 상태가 지금도 존재함을 증명할 수는 없습니다.

## 연동과 강제력 경계

현재 Core와 MCP 개발본에는 bounded query, immutable revision, transaction command, backup/restore, 공식 MCP SDK 통합, current-turn Codex provenance, Paseo current-agent/decision surface가 포함됩니다.

중요한 경계:

- 강제력은 **advisory**이며 임의 host write interception이나 same-OS-user privilege isolation을 제공하지 않습니다.
- 일반 MCP 지원만으로 인간 승인을 인증하거나 verified agent turn을 시작할 수 없습니다.
- exact-message receipt lookup이 없는 host는 uncertain delivery를 자동 해결할 수 없습니다.
- Paseo public adapter는 atomic idle-conditioned send나 confirmed interruption을 제공하지 않습니다.
- 자동/package 검사는 실제 Windows installer, live Paseo, device, production acceptance를 해당 surface에서 직접 확인하지 않는 한 증명하지 않습니다.

현재 검증 상태는 [SQLite 공통 Core 개발본](db-core.md)과 [검증과 한계](verification.md)를 확인하세요.
