# QuickHack: 업무 지식이 구현으로 이어지는 실제 사례

**QuickHack은 SKIP 개발자가 자신의 업무 문제를 해결하기 위해 만든 기기 단위 ERP/WMS입니다.** PG(기기 관리 식별자)·IMEI를 기준으로 입고 예정, 검수, 매입 확정, 재고, 판매채널 주문 매칭, 송장, 배송, 반품을 연결합니다. 이 사례는 그중 **고객 변경 요청에 따른 수동 주문 매칭**을 SKIP으로 구체화한 실제 개발 기록을 보여줍니다.

**QuickHack is a device-level ERP/WMS built by SKIP's developer for their own work.** It connects receiving, inspection, purchasing, inventory, order allocation, shipping, and returns through device identifiers. This case shows actual SKIP development records for manual order allocation in response to customer change requests.

[QuickHack 프로젝트와 업무 배경 / Project and domain background](https://github.com/msang710/QuickHack_Public_Portfolio/blob/96a8dec8131973aa07b2626f086730f757aced29/README.md)

## 현업이 결정해야 하는 문제 / Decisions that require domain knowledge

고객이 주문한 옵션과 다른 특정 기기를 요청했다면 교체를 허용해야 할까요? 관리자가 교체를 확정하는 순간 자동 주문 매칭이 같은 기기를 가져가면 누가 우선일까요? 이미 포장이나 출력이 시작된 주문도 바꿀 수 있을까요?

이 질문에 대한 답은 제품의 업무 규칙입니다. 개발자는 그 규칙을 결정하고, 에이전트는 영향 조사와 설계·구현·검증으로 연결했습니다.

Should a customer-requested device be allowed when it differs from the original offer? Who wins when a manager's replacement competes with automatic allocation? What if packing or printing has already started? These are business decisions the developer supplied; the agent translated them into investigation, design, implementation, and verification.

| 실제 제품 결정 / Recorded decision | 사용자에게 보이는 동작 / Observable behavior | 시스템으로 옮긴 규칙 / Technical consequence |
|---|---|---|
| **D-003:** 요청받은 특정 PG는 판매 오퍼 조건과 달라도 선택 가능 / Allow a requested device despite an offer mismatch | 차이를 미리 보여주고, 판매 가능 여부와 중복 배정은 별도로 검사 / Show differences; separately check availability and allocation | 오퍼 차이와 선택 가능 판정 분리 / Separate differences from eligibility |
| **D-004:** STAFF 조회, MANAGER+OTP 실행 / Staff can inspect; managers execute with OTP | 직원은 변경안을 확인하고 관리자가 확정 / Staff prepare; managers confirm | 조회·변경 권한 분리 / Separate read and mutation authorization |
| **D-010:** 이미 시작된 출고 업무 > 확정 수동 변경 > 자동 매칭 / Started downstream work > confirmed manual change > automatic matching | 이미 진행된 출고는 보호하고 자동 매칭은 수동 변경을 존중 / Protect downstream work and prioritize confirmed manual changes | 확정 실행의 임시 선점, 잠금 후 재검증, 경합 테스트 / Intent leases, locked revalidation, concurrency tests |
| **R-004:** 이전 기기 해제와 새 기기 예약은 함께 성공 / Release the previous device and reserve the replacement together | 한쪽만 바뀐 재고 상태를 남기지 않음 / No partially replaced inventory | 원장·allocation·감사의 원자적 변경 / Atomic ledger, allocation, and audit changes |

## 실제로 이런 문서가 나옵니다 / The actual document outputs

| 문서 / Document | 확인할 내용 / What it demonstrates |
|---|---|
| [요구사항 / PRD](prd.md) | 업무 경계, 사람의 결정 D-001~D-010 중 발췌, 수용 기준 R-001~R-011 / Scope, human decisions, acceptance criteria |
| [사용자 스토리 / User stories](user_stories.md) | STAFF·MANAGER·운영자의 정상 흐름과 예외, Given/When/Then / Role-specific behavior and failure cases |
| [시스템 설계 / System design](system_design.md) | D-010의 우선순위가 lease와 BM-01~BM-10 경합 행렬로 구체화됨 / Business priority becomes an intent lease and concurrency matrix |
| [실행 작업과 검증 기록 / Tasks and verification](tasks.md) | 결정·요구사항에 연결된 작업, 구현과 아직 남은 DB 검증 / Traceable tasks, implementation, and remaining DB evidence |

예를 들어 원문 US-002는 다음처럼 업무상 허용과 금지를 구분합니다.

> 예외: 오퍼 불일치는 경고지만 선택 차단이 아니다. `SELLABLE`이 아니거나 이미 예약된 PG는 차단한다.

The original US-002 distinguishes an acceptable exception from an unsafe one: an offer mismatch is a warning, while an unavailable or already allocated device is blocked.

## 문서에서 구현까지 / Follow the decisions into code

아래 링크는 QuickHack 소스 리비전 `96a8dec8131973aa07b2626f086730f757aced29`에 고정했습니다. 문서 ID는 실제 기록의 ID이며, 표의 설명은 발췌본을 안내하기 위해 작성한 요약입니다.

The links below are pinned to a QuickHack source revision. Document IDs are original; the traceability descriptions are editorial summaries.

| 연결 / Trace | 소스 근거 / Source evidence |
|---|---|
| D-003 → R-003 → US-002 | [`candidateDto`](https://github.com/msang710/QuickHack_Public_Portfolio/blob/96a8dec8131973aa07b2626f086730f757aced29/quickhack_server/sales-channel/coupang/manual-order-match-service.ts#L339): `differences`와 `eligible`을 별도로 계산 / Computes offer differences separately from eligibility |
| D-004 → R-006 → US-003 | [실행 권한 검사 / Execution authorization](https://github.com/msang710/QuickHack_Public_Portfolio/blob/96a8dec8131973aa07b2626f086730f757aced29/quickhack_server/sales-channel/coupang/manual-order-match-service.ts#L882): MANAGER와 OTP 확인 |
| D-010 → R-011 → 설계 우선순위 행렬 → T-010A | [intent lease service](https://github.com/msang710/QuickHack_Public_Portfolio/blob/96a8dec8131973aa07b2626f086730f757aced29/quickhack_server/sales-channel/coupang/manual-order-match-intent-service.ts), [BM 경합 시나리오 / Concurrency scenarios](https://github.com/msang710/QuickHack_Public_Portfolio/blob/96a8dec8131973aa07b2626f086730f757aced29/tests/integration/postgresql/test-manual-order-match-execution.mjs#L280) |
| R-004 → US-003 | [release/reserve transaction](https://github.com/msang710/QuickHack_Public_Portfolio/blob/96a8dec8131973aa07b2626f086730f757aced29/quickhack_server/sales-channel/coupang/manual-order-match-service.ts#L689): 이전 PG 해제와 새 PG 예약 / Releases the previous PG and reserves the replacement |
| R-008 → US-005 → 설계 18.1 → T-030 | [shipment safety projection](https://github.com/msang710/QuickHack_Public_Portfolio/blob/96a8dec8131973aa07b2626f086730f757aced29/quickhack_server/sales-channel/coupang/manual-order-match-shipment-safety.ts), [잠금 후 재검증 / Locked preview revalidation](https://github.com/msang710/QuickHack_Public_Portfolio/blob/96a8dec8131973aa07b2626f086730f757aced29/quickhack_server/sales-channel/coupang/manual-order-match-service.ts#L677), [정책 검사 / Policy checks](https://github.com/msang710/QuickHack_Public_Portfolio/blob/96a8dec8131973aa07b2626f086730f757aced29/tests/contracts/test-manual-order-match-source-completion.mjs) |

## 이 사례가 보여주는 것 / Why this matters for domain experts

도메인 전문가는 “어떤 예외를 허용하고, 어떤 상태에서는 멈추며, 경합하면 누구를 우선할지”를 설명할 수 있습니다. 이 사례에서는 그 설명이 결정 ID, 사용자 시나리오, 설계의 불변조건, 실행 작업과 코드로 이어집니다. README의 **자신의 업무 문제를 직접 해결하고 싶은 도메인 전문가**라는 대상 독자를 뒷받침하는 구체적인 사용 사례입니다.

Domain experts can describe acceptable exceptions, stop conditions, and operational priorities. Here, those judgments become decision IDs, user scenarios, design invariants, tasks, and code—a concrete example of SKIP's intended audience building a tool for their own work.

## 출처와 검증 범위 / Provenance and verification scope

이 문서들은 홍보용 가상 시나리오를 위해 새로 생성한 문서가 아닙니다. 외부 기록 저장소의 `manual-order-inventory-matching` 목표에서 발췌했습니다. PRD의 작성일은 2026-08-25, 제품 결정에는 2026-08-26이 기록되어 있습니다. 설계·작업 파일에는 이후 수정 단계가 누적되어 있으며, 발췌본은 README용으로 사후에 준비했습니다. 원본 frontmatter, 전체 승인 대화, 고객·직원 데이터, 내부 장애 상세 기록은 포함하지 않았습니다.

These are excerpts from actual development records, prepared afterward for this README. The PRD records creation on 2026-08-25 and product decisions on 2026-08-26; design and task files include later revisions. Original metadata, full approval conversations, customer or staff data, and internal incident details are excluded.

T-030 기록은 **SOURCE COMPLETE / DB EVIDENCE PENDING**, T-032는 **PARTIALLY VERIFIED**이며 DB·build·실제 UI 검증 전 운영 rollout을 차단한다고 명시합니다. 이 공개 사례 준비에서는 코드와 기록의 연결을 확인했으며 QuickHack의 DB·운영 검증을 재실행하지 않았습니다. 테스트 소스가 존재한다는 사실과 현재 환경에서 통과했다는 주장은 구분합니다.

The task excerpts explicitly retain **DB EVIDENCE PENDING** and **PARTIALLY VERIFIED**, with rollout blocked pending DB, build, and live UI acceptance. Preparing this case verified document-to-source links; it did not rerun QuickHack's DB or operational validation. Test source is not a current passing execution result.

한 개발자의 실제 사용 사례이며 모든 도메인 전문가의 생산성이나 운영 성공을 입증하는 연구는 아닙니다. 당시 워크플로와 기록의 활용을 보여주며 현재 SKIP의 모든 runtime 기능이 당시 사용되었다고 주장하지 않습니다.

This is one developer's real usage case, not a study establishing productivity or operational success for every domain expert. It demonstrates the workflow and records used, without claiming every current SKIP runtime feature existed or was used at that time.
