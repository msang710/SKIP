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
