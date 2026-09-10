# QuickHack — 이관된 목표 기록

[사례 안내](README.md) · [사례 DB](case.db) · [이관 검증](migration.json)

> 현재 Core의 record.list / record 조회 결과로 생성한 읽기 전용 공개 뷰입니다. 수정 원본은 사례 DB입니다. 과거 발췌 기록의 이관이며 현재 승인·검증 결과가 아닙니다.

> Read-only publication view generated from Core queries. Migrated historical excerpts, not fresh approval or verification.

## 기록 목록

| 유형 | 기록 | 당시 상태 |
|---|---|---|
| 목표 | [goal](#record-0) | UNSPECIFIED |
| 제품 결정 | [D-001](#record-1) | confirmed |
| 제품 결정 | [D-002](#record-2) | confirmed |
| 제품 결정 | [D-003](#record-3) | confirmed |
| 제품 결정 | [D-004](#record-4) | confirmed |
| 제품 결정 | [D-005](#record-5) | confirmed |
| 제품 결정 | [D-006](#record-6) | confirmed |
| 제품 결정 | [D-007](#record-7) | confirmed |
| 제품 결정 | [D-008](#record-8) | confirmed |
| 제품 결정 | [D-010](#record-9) | confirmed |
| 요구사항 | [R-001](#record-10) | UNSPECIFIED |
| 요구사항 | [R-002](#record-11) | UNSPECIFIED |
| 요구사항 | [R-003](#record-12) | UNSPECIFIED |
| 요구사항 | [R-004](#record-13) | UNSPECIFIED |
| 요구사항 | [R-005](#record-14) | UNSPECIFIED |
| 요구사항 | [R-006](#record-15) | UNSPECIFIED |
| 요구사항 | [R-007](#record-16) | UNSPECIFIED |
| 요구사항 | [R-008](#record-17) | UNSPECIFIED |
| 요구사항 | [R-009](#record-18) | UNSPECIFIED |
| 요구사항 | [R-010](#record-19) | UNSPECIFIED |
| 요구사항 | [R-011](#record-20) | UNSPECIFIED |
| 요구사항 | [user_stories-0](#record-21) | UNSPECIFIED |
| 요구사항 | [user_stories-1](#record-22) | UNSPECIFIED |
| 요구사항 | [user_stories-2](#record-23) | UNSPECIFIED |
| 요구사항 | [user_stories-3](#record-24) | UNSPECIFIED |
| 설계 | [system_design-0](#record-25) | UNSPECIFIED |
| 작업 | [T-010A](#record-26) | UNSPECIFIED |
| 작업 | [T-030](#record-27) | UNSPECIFIED |
| 작업 | [T-032](#record-28) | UNSPECIFIED |

<a id="record-0"></a>

## 목표 · goal

기록 revision: 2 · 당시 상태: UNSPECIFIED

**title**

QuickHack — prd.md 발췌

**intent**

# 목표

권한 있는 직원이 판매채널에 이미 접수된 주문의 고객 변경 요청을 확인하고, 요청 내용에 맞는 특정 PG를 직접 배정·교체·해제하여 기존 주문의 출고·매출 흐름을 정확히 이어간다.

# 목표 동작

1. 직원이 판매채널 주문·출고·품목을 검색한다.
2. 현재 allocation, 주문 조건, 변경 요청 접수 경로와 사유, downstream 상태를 확인한다.
3. 요청에 맞는 exact PG를 검색하고, 오퍼 불일치를 포함한 변경 전후 영향을 preview한다.
4. MANAGER가 OTP로 assign/replace/release를 확정한다.
5. 서버가 최신 상태를 잠금·재검증하고 재고 원장, allocation, 작업 상태, 감사를 원자 반영한다.
6. 변경된 allocation은 기존 주문의 상품준비중, 포장, 송장, 배송, 반품, 매출 흐름으로 진행한다.

**success_definition**

원문에 명시되지 않음


<a id="record-1"></a>

## 제품 결정 · D-001

기록 revision: 1 · 당시 상태: confirmed

**question**

대상은 판매채널에 이미 존재하는 주문의 고객 변경 요청이다.

**rationale**

| ID | Date | Decision | Status |
| D-001 | 2026-08-26 | 대상은 판매채널에 이미 존재하는 주문의 고객 변경 요청이다. | confirmed |

**risk_summary**

원문에 명시되지 않음


<a id="record-2"></a>

## 제품 결정 · D-002

기록 revision: 1 · 당시 상태: confirmed

**question**

쿠팡 문의·유선 문의·기타는 주문 출처가 아니라 변경 요청 접수 경로다.

**rationale**

| ID | Date | Decision | Status |
| D-002 | 2026-08-26 | 쿠팡 문의·유선 문의·기타는 주문 출처가 아니라 변경 요청 접수 경로다. | confirmed |

**risk_summary**

원문에 명시되지 않음


<a id="record-3"></a>

## 제품 결정 · D-003

기록 revision: 1 · 당시 상태: confirmed

**question**

요청받은 특정 PG는 판매 오퍼 조건과 달라도 선택할 수 있다. 그 결과 다른 주문 후보와 매출 통계가 달라지는 것은 정상이다.

**rationale**

| ID | Date | Decision | Status |
| D-003 | 2026-08-26 | 요청받은 특정 PG는 판매 오퍼 조건과 달라도 선택할 수 있다. 그 결과 다른 주문 후보와 매출 통계가 달라지는 것은 정상이다. | confirmed |

**risk_summary**

원문에 명시되지 않음


<a id="record-4"></a>

## 제품 결정 · D-004

기록 revision: 1 · 당시 상태: confirmed

**question**

조회는 STAFF 이상, assign/replace/release는 MANAGER 이상과 `CHANNEL_ORDER_MATCHING` OTP를 요구한다.

**rationale**

| ID | Date | Decision | Status |
| D-004 | 2026-08-26 | 조회는 STAFF 이상, assign/replace/release는 MANAGER 이상과 `CHANNEL_ORDER_MATCHING` OTP를 요구한다. | confirmed |

**risk_summary**

원문에 명시되지 않음


<a id="record-5"></a>

## 제품 결정 · D-005

기록 revision: 1 · 당시 상태: confirmed

**question**

배정 해제 후 `PARTIAL/UNMATCHED` 상태로 남기는 것을 허용하며 사유와 명시적 확인을 요구한다.

**rationale**

| ID | Date | Decision | Status |
| D-005 | 2026-08-26 | 배정 해제 후 `PARTIAL/UNMATCHED` 상태로 남기는 것을 허용하며 사유와 명시적 확인을 요구한다. | confirmed |

**risk_summary**

원문에 명시되지 않음


<a id="record-6"></a>

## 제품 결정 · D-006

기록 revision: 1 · 당시 상태: confirmed

**question**

변경 후 기존 matching post-cycle과 출고 lifecycle을 계속 사용한다.

**rationale**

| ID | Date | Decision | Status |
| D-006 | 2026-08-26 | 변경 후 기존 matching post-cycle과 출고 lifecycle을 계속 사용한다. | confirmed |

**risk_summary**

원문에 명시되지 않음


<a id="record-7"></a>

## 제품 결정 · D-007

기록 revision: 1 · 당시 상태: confirmed

**question**

동일 명령은 1회 효과를 보장하고 접수 경로·담당자·사유·before/after를 감사한다.

**rationale**

| ID | Date | Decision | Status |
| D-007 | 2026-08-26 | 동일 명령은 1회 효과를 보장하고 접수 경로·담당자·사유·before/after를 감사한다. | confirmed |

**risk_summary**

원문에 명시되지 않음


<a id="record-8"></a>

## 제품 결정 · D-008

기록 revision: 1 · 당시 상태: confirmed

**question**

판매채널 주문이 없는 독립 출고는 이 메뉴의 비범위이며 재고 수정 메뉴의 `보류` 상태로 처리한다.

**rationale**

| ID | Date | Decision | Status |
| D-008 | 2026-08-26 | 판매채널 주문이 없는 독립 출고는 이 메뉴의 비범위이며 재고 수정 메뉴의 `보류` 상태로 처리한다. | confirmed |

**risk_summary**

원문에 명시되지 않음


<a id="record-9"></a>

## 제품 결정 · D-010

기록 revision: 1 · 당시 상태: confirmed

**question**

충돌 우선순위는 `이미 시작된 외부 acknowledgement·포장·출력·반품 > 확정 실행된 직원 수동 변경 > 자동 matcher·전체 rematch`로 한다. 같은 등급의 직원 명령은 먼저 커밋한 명령을 우선한다.

**rationale**

| ID | Date | Decision | Status |
| D-010 | 2026-08-26 | 충돌 우선순위는 `이미 시작된 외부 acknowledgement·포장·출력·반품 > 확정 실행된 직원 수동 변경 > 자동 matcher·전체 rematch`로 한다. 같은 등급의 직원 명령은 먼저 커밋한 명령을 우선한다. | confirmed |

**risk_summary**

원문에 명시되지 않음


<a id="record-10"></a>

## 요구사항 · R-001

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-001 / AC-001: 기존 채널 주문 품목과 수량 슬롯별 allocation을 조회하고 exact PG를 선택한다.

**statement**

- R-001 / AC-001: 기존 채널 주문 품목과 수량 슬롯별 allocation을 조회하고 exact PG를 선택한다.

**rationale**

원문에 명시되지 않음


<a id="record-11"></a>

## 요구사항 · R-002

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-002 / AC-002: 요청 접수 경로와 변경 사유를 필수 기록하고 동일 원문을 allocation provenance와 직원 활동 감사 기록에 보존한다.

**statement**

- R-002 / AC-002: 요청 접수 경로와 변경 사유를 필수 기록하고 동일 원문을 allocation provenance와 직원 활동 감사 기록에 보존한다.

**rationale**

원문에 명시되지 않음


<a id="record-12"></a>

## 요구사항 · R-003

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-003 / AC-003: 오퍼 불일치 PG도 허용하되 preview에서 주문 조건, 선택 PG, 재고·통계 영향을 명확히 표시한다.

**statement**

- R-003 / AC-003: 오퍼 불일치 PG도 허용하되 preview에서 주문 조건, 선택 PG, 재고·통계 영향을 명확히 표시한다.

**rationale**

원문에 명시되지 않음


<a id="record-13"></a>

## 요구사항 · R-004

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-004 / AC-004: 교체 성공 시 이전 PG는 `SELLABLE`, 새 PG는 `RESERVED`이며 어느 한쪽만 반영될 수 없다.

**statement**

- R-004 / AC-004: 교체 성공 시 이전 PG는 `SELLABLE`, 새 PG는 `RESERVED`이며 어느 한쪽만 반영될 수 없다.

**rationale**

원문에 명시되지 않음


<a id="record-14"></a>

## 요구사항 · R-005

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-005 / AC-005: stale preview, 수량 초과, worker 경합에서는 전체 rollback되고 refresh를 요구한다.

**statement**

- R-005 / AC-005: stale preview, 수량 초과, worker 경합에서는 전체 rollback되고 refresh를 요구한다.

**rationale**

원문에 명시되지 않음


<a id="record-15"></a>

## 요구사항 · R-006

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-006 / AC-006: STAFF 조회와 MANAGER+OTP mutation 권한이 메뉴와 API에서 일치한다.

**statement**

- R-006 / AC-006: STAFF 조회와 MANAGER+OTP mutation 권한이 메뉴와 API에서 일치한다.

**rationale**

원문에 명시되지 않음


<a id="record-16"></a>

## 요구사항 · R-007

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-007 / AC-007: 변경된 allocation이 기존 주문의 downstream 흐름과 매출 통계에 반영된다.

**statement**

- R-007 / AC-007: 변경된 allocation이 기존 주문의 downstream 흐름과 매출 통계에 반영된다.

**rationale**

원문에 명시되지 않음


<a id="record-17"></a>

## 요구사항 · R-008

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-008 / AC-008: 물리 출고가 이미 진행돼 안전하게 변경할 수 없으면 강제 수정하지 않고 해당 복구 흐름을 안내한다.

**statement**

- R-008 / AC-008: 물리 출고가 이미 진행돼 안전하게 변경할 수 없으면 강제 수정하지 않고 해당 복구 흐름을 안내한다.

**rationale**

원문에 명시되지 않음


<a id="record-18"></a>

## 요구사항 · R-009

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-009 / AC-009: 판매채널 주문 식별자가 없는 대상은 mutation 0건으로 거부하고 `재고 수정 > 보류`를 안내한다.

**statement**

- R-009 / AC-009: 판매채널 주문 식별자가 없는 대상은 mutation 0건으로 거부하고 `재고 수정 > 보류`를 안내한다.

**rationale**

원문에 명시되지 않음


<a id="record-19"></a>

## 요구사항 · R-010

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-010 / AC-010: 동일 idempotency key/payload 재시도는 중복 allocation과 원장 movement를 만들지 않는다.

**statement**

- R-010 / AC-010: 동일 idempotency key/payload 재시도는 중복 allocation과 원장 movement를 만들지 않는다.

**rationale**

원문에 명시되지 않음


<a id="record-20"></a>

## 요구사항 · R-011

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

R-011 / AC-011: 확정 수동 명령이 활성인 shipment/PG는 아직 시작되지 않은 auto matcher와 전체 rematch가 건너뛰며, 이미 시작된 external/downstream 업무가 있으면 수동 명령이 stable conflict로 중단된다.

**statement**

- R-011 / AC-011: 확정 수동 명령이 활성인 shipment/PG는 아직 시작되지 않은 auto matcher와 전체 rematch가 건너뛰며, 이미 시작된 external/downstream 업무가 있으면 수동 명령이 stable conflict로 중단된다.

**rationale**

원문에 명시되지 않음


<a id="record-21"></a>

## 요구사항 · user_stories-0

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

QuickHack — user_stories.md 발췌

**statement**

# QuickHack — user_stories.md 발췌

[사례 안내 / Case study](README.md)

판매채널 주문 변경 요청·PG 수동 매칭의 실제 개발 기록에서 선택한 절입니다. 원문의 제목·ID·본문을 유지했습니다. 다른 절과 frontmatter는 생략했습니다.

These are selected sections from actual development records, retaining the original Korean, headings, and IDs. Omitted sections and metadata are not reproduced. This is a documentation copy, not a live approval or operational status record.

---

**rationale**

원문에 명시되지 않음


<a id="record-22"></a>

## 요구사항 · user_stories-1

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

US-002 요청과 후보 PG preview

**statement**

# US-002 요청과 후보 PG preview

STAFF로서 변경 요청 접수 경로와 사유를 기록하고 특정 PG 선택의 영향을 확인하여 관리자에게 정확한 변경안을 전달하고 싶다.

- 연결 결정: D-002, D-003
- 정상 흐름: 접수 경로, 제한된 사유, exact PG를 입력하고 주문 조건 대비 차이와 재고 영향을 본다.
- 예외: 오퍼 불일치는 경고지만 선택 차단이 아니다. `SELLABLE`이 아니거나 이미 예약된 PG는 차단한다.
- 감사: 입력한 사유 원문은 allocation provenance와 직원 활동 감사 기록에 동일하게 보존한다.

Given 기존 주문과 `SELLABLE` PG가 있을 때, When 사용자가 preview하면, Then 이전/이후 PG, 오퍼 차이, 후보 재고 감소, 허용 여부와 manifest가 반환된다.

**rationale**

원문에 명시되지 않음

### decisions

- **decision_id**: [record-470d102716c3087d5aeec6392db0a0203402](#record-2)
- **decision_revision**: 1
- **rationale**: 원문 명시: D-002

- **decision_id**: [record-caefae4ab7c871dcceaf96562765293e1439](#record-3)
- **decision_revision**: 1
- **rationale**: 원문 명시: D-003


<a id="record-23"></a>

## 요구사항 · user_stories-2

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

US-003 PG 배정·교체

**statement**

# US-003 PG 배정·교체

MANAGER로서 OTP 확인 후 특정 PG를 배정 또는 교체하여 고객 변경 요청을 실제 출고 재고에 반영하고 싶다.

- 연결 결정: D-003, D-004, D-006, D-007
- 정상 흐름: preview manifest, expected revisions, idempotency key, 요청 경로와 사유로 실행한다.
- 수량: 활성 allocation 수는 `matchable_quantity`를 넘지 않는다.
- 부분 실패: 이전 PG release와 새 PG reserve 및 allocation 변경 중 하나라도 실패하면 전체 rollback한다.
- 경합: 자동 worker나 다른 관리자가 먼저 변경하면 0건 처리하고 refresh를 요구한다.
- 중복: 동일 key/payload 재시도는 동일 결과를 반환한다.

Given 유효한 preview와 OTP가 있을 때, When MANAGER가 실행하면, Then 이전 PG와 새 PG의 원장·allocation·work status·감사가 한 transaction으로 확정된다.

**rationale**

원문에 명시되지 않음

### decisions

- **decision_id**: [record-08bcb85d94f6fadc5e11f68254fe0b3bcbe4](#record-6)
- **decision_revision**: 1
- **rationale**: 원문 명시: D-006

- **decision_id**: [record-22b6c6fcefef357a909d64af59c8ef623cda](#record-7)
- **decision_revision**: 1
- **rationale**: 원문 명시: D-007

- **decision_id**: [record-caefae4ab7c871dcceaf96562765293e1439](#record-3)
- **decision_revision**: 1
- **rationale**: 원문 명시: D-003

- **decision_id**: [record-fffc30b534579d4ffb0f7bc776c85c01692a](#record-4)
- **decision_revision**: 1
- **rationale**: 원문 명시: D-004


<a id="record-24"></a>

## 요구사항 · user_stories-3

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

US-005 downstream 안전성

**statement**

# US-005 downstream 안전성

운영자로서 이미 물리 출고가 진행된 주문을 잘못 소급 변경하지 않고 적절한 복구 흐름을 안내받고 싶다.

- 연결 결정: D-006
- 차단: 출력 차수, 활성 포장, 진행 중 외부 쓰기, 송장, 반품, 매출 등 비가역 관계를 서버가 판정한다.
- 복구: 차단 사유와 포장 해제·송장 교체·반품 등 다음 행동을 보여준다.

Given downstream handoff가 시작된 allocation일 때, When preview 또는 execute하면, Then 변화 0건과 안정적인 reason code 및 복구 안내가 반환된다.

**rationale**

원문에 명시되지 않음

### decisions

- **decision_id**: [record-08bcb85d94f6fadc5e11f68254fe0b3bcbe4](#record-6)
- **decision_revision**: 1
- **rationale**: 원문 명시: D-006


<a id="record-25"></a>

## 설계 · system_design-0

기록 revision: 1 · 당시 상태: UNSPECIFIED

**title**

QuickHack — system_design.md 발췌

**design_body**

# QuickHack — system_design.md 발췌

[사례 안내 / Case study](README.md)

판매채널 주문 변경 요청·PG 수동 매칭의 실제 개발 기록에서 선택한 절입니다. 원문의 제목·ID·본문을 유지했습니다. 다른 절과 frontmatter는 생략했습니다. 문서에 누적된 여러 수정 단계의 발췌이며, 하나의 시점에 작성된 최초 설계로 해석하지 않습니다.

These are selected sections from actual development records, retaining the original Korean, headings, and IDs. Omitted sections and metadata are not reproduced. This is a documentation copy, not a live approval or operational status record.

---

### 짧은 manual intent lease

확정 실행 시점에만 shipment와 대상 PG에 결합된 짧은 TTL의 durable intent lease를 획득한다. preview는 lease를 만들지 않는다. lease는 `command id`, 사용자, shipment, 대상 PG 집합, 생성·만료 시각을 포함한다.

- auto matcher와 전체 rematch는 mutation 시작 전에 활성 manual lease를 확인하고 해당 shipment/PG를 건너뛴다.
- instruct acknowledgement, 포장, 출력, 반품은 manual lease에 의해 지연되지 않는다.
- manual execute는 이들 downstream 상태를 잠금 후 재검증하고 이미 시작됐으면 stable conflict로 전체 rollback한다.
- 같은 등급의 manual 명령은 별도의 강제 선점 없이 DB commit 순서와 revision/unique conflict를 따른다.
- 프로세스 종료나 client 이탈 뒤에는 TTL 만료로 자동 해제한다. 성공·명시적 실패 시 즉시 종료 상태로 전환한다.

### 우선순위 행렬

| ID | 경합 | 고정 barrier | 기대 winner | loser 결과 | 핵심 불변식 |
|---|---|---|---|---|---|
| BM-01 | manual ASSIGN vs auto matcher, 같은 PG | 양쪽 `BEFORE_DOMAIN_LOCK`, manual lease 획득 후 auto 진행 | manual | auto skip/reselect | 활성 allocation 1, movement 1쌍 |
| BM-02 | manual REPLACE vs 전체 rematch, 같은 shipment | 양쪽 `AFTER_SNAPSHOT`, manual lease 획득 후 rematch 진행 | manual | rematch shipment skip | 이전 PG SELLABLE, 새 PG RESERVED |
| BM-03 | manual RELEASE vs instruct acknowledgement | instruct `AFTER_DOMAIN_LOCK`, manual 시작 | instruct | manual stale/downstream conflict | ack와 recovery 의미 혼합 없음 |
| BM-04 | manual REPLACE vs shipment print | print `AFTER_DOMAIN_LOCK`, manual 시작 | print | `SHIPMENT_LIST_PRINTED` | 출력 snapshot과 allocation 일치 |
| BM-05 | manual REPLACE vs packing | packing `AFTER_DOMAIN_LOCK`, manual 시작 | packing | `ACTIVE_PACKAGE_GROUP` 또는 packing conflict | 스캔 PG와 allocation 일치 |
| BM-06 | manual RELEASE vs return finalizer | return `AFTER_DOMAIN_LOCK`, manual 시작 | return | `RETURN_STARTED` | 반품 책임 allocation 보존 |
| BM-07 | manual ASSIGN vs inventory correction, 같은 PG | 둘 다 `BEFORE_DOMAIN_LOCK` | 먼저 lock/commit한 직원 명령 | stable inventory conflict | revision 1회 증가, 부분 movement 0 |
| BM-08 | manual vs manual, 같은 PG | 둘 다 `BEFORE_DOMAIN_LOCK` | 먼저 commit한 명령 | stale/unique conflict | 활성 allocation 1 |
| BM-09 | reversed balance keys | 첫 balance plan 준비 후 동시 해제 | 직렬화된 두 유효 결과 또는 한 conflict | bounded retry | deadlock 0, balance 합계 보존 |
| BM-10 | lease owner 프로세스 종료 | `AFTER_INTENT_ACQUIRE`에서 owner 종료 | TTL 이후 새 명령 | 만료 전 auto skip | 영구 starvation 없음 |

## 18.1 shipment/carrier safety projection 공통화

현재 manual preview는 shipment의 active allocation, package-group membership, sales record, return allocation, channel write target을 검사한다. active package group은 이미 변경을 차단하지만 다음 상태는 하나의 revisioned snapshot으로 정규화되지 않았다.

- allocation에 직접 연결된 legacy `carrier_shipments`
- package group의 current/all carrier shipment와 invoice/shipment revision
- `carrier_invoice_issue_items` 및 issue batch 상태
- `carrier_shipment_registration_works`
- `carrier_invoice_replacement_works`
- shipment address-change work와 carrier return request

새 `manual-order-match-shipment-safety.ts`는 shipment와 allocation ID 집합을 입력받아 다음의 정렬된 projection을 반환한다.

```text
work item id/revision/status
allocation id/status/PG
package group id/revision/status/current shipment
carrier shipment id/revision/invoice status/shipment status
invoice issue item/batch id/status/label status
registration work id/revision/status/execution ownership
replacement work id/version/status/stage
address-change work id/status/revision
return/write conflict ids
```

- status 문자열을 manual service에서 새로 복제하지 않고 `quickhack_shared/shipment/*`의 공통 상수와 각 carrier workflow의 terminal/active 판정을 재사용하거나 해당 판정을 shared policy로 승격한다.
- 존재하는 비가역 carrier shipment, active/review-required carrier workflow, active package group, 배송·반품·매출 증거는 fail-closed blocker다.
- 취소·무효화된 workflow의 역사적 행만 존재하는 경우에는 새 blocker를 만들지 않되 snapshot에는 포함해 preview 이후 재활성화/교체를 탐지한다.
- preview manifest에는 전체 projection hash와 blocker code를 넣는다. execute는 업무 root와 allocation/PG/balance lock을 얻은 뒤 같은 projection을 다시 읽고 hash가 다르면 ledger mutation 전에 `STALE_PREVIEW`로 중단한다.
- 새 DB column이나 migration은 추가하지 않는다.

**scope_description**

원문에 명시되지 않음

**alternatives_body**

원문에 명시되지 않음

**rollback_body**

원문에 명시되지 않음

### items

- **item_id**: part-0
- **title**: QuickHack — system_design.md 발췌
- **design_body**: # QuickHack — system_design.md 발췌

[사례 안내 / Case study](README.md)

판매채널 주문 변경 요청·PG 수동 매칭의 실제 개발 기록에서 선택한 절입니다. 원문의 제목·ID·본문을 유지했습니다. 다른 절과 frontmatter는 생략했습니다. 문서에 누적된 여러 수정 단계의 발췌이며, 하나의 시점에 작성된 최초 설계로 해석하지 않습니다.

These are selected sections from actual development records, retaining the original Korean, headings, and IDs. Omitted sections and metadata are not reproduced. This is a documentation copy, not a live approval or operational status record.

---
- **verification_body**: 원문에 명시되지 않음
- **position**: 0

- **item_id**: part-1
- **title**: 짧은 manual intent lease
- **design_body**: ### 짧은 manual intent lease

확정 실행 시점에만 shipment와 대상 PG에 결합된 짧은 TTL의 durable intent lease를 획득한다. preview는 lease를 만들지 않는다. lease는 `command id`, 사용자, shipment, 대상 PG 집합, 생성·만료 시각을 포함한다.

- auto matcher와 전체 rematch는 mutation 시작 전에 활성 manual lease를 확인하고 해당 shipment/PG를 건너뛴다.
- instruct acknowledgement, 포장, 출력, 반품은 manual lease에 의해 지연되지 않는다.
- manual execute는 이들 downstream 상태를 잠금 후 재검증하고 이미 시작됐으면 stable conflict로 전체 rollback한다.
- 같은 등급의 manual 명령은 별도의 강제 선점 없이 DB commit 순서와 revision/unique conflict를 따른다.
- 프로세스 종료나 client 이탈 뒤에는 TTL 만료로 자동 해제한다. 성공·명시적 실패 시 즉시 종료 상태로 전환한다.
- **verification_body**: 원문에 명시되지 않음
- **position**: 1

- **item_id**: part-2
- **title**: 우선순위 행렬
- **design_body**: ### 우선순위 행렬

| ID | 경합 | 고정 barrier | 기대 winner | loser 결과 | 핵심 불변식 |
|---|---|---|---|---|---|
| BM-01 | manual ASSIGN vs auto matcher, 같은 PG | 양쪽 `BEFORE_DOMAIN_LOCK`, manual lease 획득 후 auto 진행 | manual | auto skip/reselect | 활성 allocation 1, movement 1쌍 |
| BM-02 | manual REPLACE vs 전체 rematch, 같은 shipment | 양쪽 `AFTER_SNAPSHOT`, manual lease 획득 후 rematch 진행 | manual | rematch shipment skip | 이전 PG SELLABLE, 새 PG RESERVED |
| BM-03 | manual RELEASE vs instruct acknowledgement | instruct `AFTER_DOMAIN_LOCK`, manual 시작 | instruct | manual stale/downstream conflict | ack와 recovery 의미 혼합 없음 |
| BM-04 | manual REPLACE vs shipment print | print `AFTER_DOMAIN_LOCK`, manual 시작 | print | `SHIPMENT_LIST_PRINTED` | 출력 snapshot과 allocation 일치 |
| BM-05 | manual REPLACE vs packing | packing `AFTER_DOMAIN_LOCK`, manual 시작 | packing | `ACTIVE_PACKAGE_GROUP` 또는 packing conflict | 스캔 PG와 allocation 일치 |
| BM-06 | manual RELEASE vs return finalizer | return `AFTER_DOMAIN_LOCK`, manual 시작 | return | `RETURN_STARTED` | 반품 책임 allocation 보존 |
| BM-07 | manual ASSIGN vs inventory correction, 같은 PG | 둘 다 `BEFORE_DOMAIN_LOCK` | 먼저 lock/commit한 직원 명령 | stable inventory conflict | revision 1회 증가, 부분 movement 0 |
| BM-08 | manual vs manual, 같은 PG | 둘 다 `BEFORE_DOMAIN_LOCK` | 먼저 commit한 명령 | stale/unique conflict | 활성 allocation 1 |
| BM-09 | reversed balance keys | 첫 balance plan 준비 후 동시 해제 | 직렬화된 두 유효 결과 또는 한 conflict | bounded retry | deadlock 0, balance 합계 보존 |
| BM-10 | lease owner 프로세스 종료 | `AFTER_INTENT_ACQUIRE`에서 owner 종료 | TTL 이후 새 명령 | 만료 전 auto skip | 영구 starvation 없음 |
- **verification_body**: 원문에 명시되지 않음
- **position**: 2

- **item_id**: part-3
- **title**: 18.1 shipment/carrier safety projection 공통화
- **design_body**: ## 18.1 shipment/carrier safety projection 공통화

현재 manual preview는 shipment의 active allocation, package-group membership, sales record, return allocation, channel write target을 검사한다. active package group은 이미 변경을 차단하지만 다음 상태는 하나의 revisioned snapshot으로 정규화되지 않았다.

- allocation에 직접 연결된 legacy `carrier_shipments`
- package group의 current/all carrier shipment와 invoice/shipment revision
- `carrier_invoice_issue_items` 및 issue batch 상태
- `carrier_shipment_registration_works`
- `carrier_invoice_replacement_works`
- shipment address-change work와 carrier return request

새 `manual-order-match-shipment-safety.ts`는 shipment와 allocation ID 집합을 입력받아 다음의 정렬된 projection을 반환한다.

```text
work item id/revision/status
allocation id/status/PG
package group id/revision/status/current shipment
carrier shipment id/revision/invoice status/shipment status
invoice issue item/batch id/status/label status
registration work id/revision/status/execution ownership
replacement work id/version/status/stage
address-change work id/status/revision
return/write conflict ids
```

- status 문자열을 manual service에서 새로 복제하지 않고 `quickhack_shared/shipment/*`의 공통 상수와 각 carrier workflow의 terminal/active 판정을 재사용하거나 해당 판정을 shared policy로 승격한다.
- 존재하는 비가역 carrier shipment, active/review-required carrier workflow, active package group, 배송·반품·매출 증거는 fail-closed blocker다.
- 취소·무효화된 workflow의 역사적 행만 존재하는 경우에는 새 blocker를 만들지 않되 snapshot에는 포함해 preview 이후 재활성화/교체를 탐지한다.
- preview manifest에는 전체 projection hash와 blocker code를 넣는다. execute는 업무 root와 allocation/PG/balance lock을 얻은 뒤 같은 projection을 다시 읽고 hash가 다르면 ledger mutation 전에 `STALE_PREVIEW`로 중단한다.
- 새 DB column이나 migration은 추가하지 않는다.
- **verification_body**: 원문에 명시되지 않음
- **position**: 3


<a id="record-26"></a>

## 작업 · T-010A

기록 revision: 1 · 당시 상태: UNSPECIFIED

**operation**

implement

**title**

T-010A manual intent lease와 결정적 우선순위 검증

**instruction_body**

## T-010A manual intent lease와 결정적 우선순위 검증

- Purpose: D-010의 `downstream > manual > auto/rematch` 우선순위를 DB 실행 결과로 고정한다.
- Dependencies: T-005~T-010.
- Target files or symbols: 신규 manual intent lease model/migration/service; auto matcher/rematch skip predicate; test-only barrier harness; `tests/integration/postgresql/test-manual-order-match-priority-concurrency.mjs`.
- Change: 확정 실행 전 TTL lease를 획득하고 auto/rematch만 이를 존중하게 한다. BM-01~BM-10을 결정적 barrier, 고정 seed 30회, randomized soak 100회로 실행한다.
- Completion conditions: BM-01~06의 winner가 D-010과 일치하고, BM-07~09는 직렬화·stable conflict로 수렴하며, BM-10에서 TTL 이후 자동 흐름이 재개된다.
- Verification: iteration JSON artifact; deadlock 0; retry budget 초과 0; 활성 allocation≤1; balance·work·recovery·downstream 일치; 부분 ledger/audit 0.
- Connected requirements: D-010, R-011/AC-011, CR-006~CR-011.

**completion_definition**

BM-01~06의 winner가 D-010과 일치하고, BM-07~09는 직렬화·stable conflict로 수렴하며, BM-10에서 TTL 이후 자동 흐름이 재개된다.

**workflow_depth**

full

**request_id**

24de48c480394ce09ad75edbfbd1d786

### checks

- **check_id**: verification
- **description**: iteration JSON artifact; deadlock 0; retry budget 초과 0; 활성 allocation≤1; balance·work·recovery·downstream 일치; 부분 ledger/audit 0.
- **surface**: source
- **required**: 1

### requirements

- **requirement_id**: [record-ceeea16eca804cdb4c0bc8de0b68649c78a6](#record-20)
- **requirement_revision**: 1
- **rationale**: 원문 명시: R-011


<a id="record-27"></a>

## 작업 · T-030

기록 revision: 1 · 당시 상태: UNSPECIFIED

**operation**

implement

**title**

T-030 preview/execute safety projection 통합

**instruction_body**

## T-030 preview/execute safety projection 통합

- Purpose: preview 이후 carrier/downstream 상태 변경을 ledger mutation 전에 차단한다.
- Dependencies: T-029.
- Target files or symbols: `previewManualOrderMatch`; execute transaction의 preview replay; API reason mapping; manual view reason labels.
- Change: projection hash와 blocker code를 manifest에 포함하고 locked execute 재조회에서 불일치 시 `STALE_PREVIEW`를 반환한다. 기존 blocker code와 오류 계약을 유지한다.
- Completion conditions: preview 시점 active carrier flow는 실행 불가, preview 이후 상태 변화는 inventory/allocation/ledger/audit 0건으로 rollback, terminal/canceled history-only fixture는 기존 허용 결과를 보존한다.
- Verification: service contract fixtures와 PostgreSQL integration 시나리오 정의; 이번 source 단계에서는 type/static checks까지 실행한다.
- Connected requirements: CR-021/022/024/032, D-004/D-005.

## T-030 — SOURCE COMPLETE / DB EVIDENCE PENDING

- preview snapshot과 manifest에 shipment safety projection 및 blocker를 포함했다.
- execute의 기존 locked preview replay가 carrier projection 변화도 mutation 전에 stale 처리한다.
- UI reason label에 carrier shipment/operation/address-change blocker를 추가했다.
- 실제 PostgreSQL 상태 변경/rollback fixture는 테스트 DB URL 부재로 NOT_RUN이다.

**completion_definition**

preview 시점 active carrier flow는 실행 불가, preview 이후 상태 변화는 inventory/allocation/ledger/audit 0건으로 rollback, terminal/canceled history-only fixture는 기존 허용 결과를 보존한다.

**workflow_depth**

full

**request_id**

24de48c480394ce09ad75edbfbd1d786

### checks

- **check_id**: verification
- **description**: service contract fixtures와 PostgreSQL integration 시나리오 정의; 이번 source 단계에서는 type/static checks까지 실행한다.
- **surface**: source
- **required**: 1


<a id="record-28"></a>

## 작업 · T-032

기록 revision: 1 · 당시 상태: UNSPECIFIED

**operation**

implement

**title**

T-032 — PARTIALLY VERIFIED

**instruction_body**

## T-032 — PARTIALLY VERIFIED

- PASS: TypeScript, carrier typecheck, focused ESLint, manual source completion/scope contracts, verification graph, test source layout, Logen label regression, `git diff --check`.
- NOT_RUN: PostgreSQL carrier-state stale/rollback, actual writer concurrency, production build, 실제 UI/OTP.

Review verdict: **NEEDS_WORK** — source 구현은 완료됐지만 실행 환경 검증은 남았다.

Implementation gate: **BLOCKED** — DB/build/UI acceptance 전 운영 rollout 금지.

**completion_definition**

원문에 명시되지 않음

**workflow_depth**

full

**request_id**

24de48c480394ce09ad75edbfbd1d786
