# QuickHack — prd.md 발췌

[사례 안내 / Case study](README.md)

판매채널 주문 변경 요청·PG 수동 매칭의 실제 개발 기록에서 선택한 절입니다. 원문의 제목·ID·본문을 유지했습니다. 다른 절과 frontmatter는 생략했습니다. 제품 결정 표에서는 이 사례와 직접 관계없는 D-009 행을 생략했습니다.

These are selected sections from actual development records, retaining the original Korean, headings, and IDs. Omitted sections and metadata are not reproduced. This is a documentation copy, not a live approval or operational status record.

---

# 목표

권한 있는 직원이 판매채널에 이미 접수된 주문의 고객 변경 요청을 확인하고, 요청 내용에 맞는 특정 PG를 직접 배정·교체·해제하여 기존 주문의 출고·매출 흐름을 정확히 이어간다.

# 제품 정의

- 주문 원천: 쿠팡 등 기존 판매채널 주문.
- 변경 요청 접수 경로: 쿠팡 문의, 유선 문의, 기타 고객 응대 경로.
- 메뉴 역할: 판매채널 주문의 실제 출고 PG를 직원이 명시적으로 변경.
- 독립 출고: 판매채널 주문이 전혀 없으면 이 메뉴에서 주문을 생성하지 않고 `재고 수정 > 보류`를 사용.

# 목표 동작

1. 직원이 판매채널 주문·출고·품목을 검색한다.
2. 현재 allocation, 주문 조건, 변경 요청 접수 경로와 사유, downstream 상태를 확인한다.
3. 요청에 맞는 exact PG를 검색하고, 오퍼 불일치를 포함한 변경 전후 영향을 preview한다.
4. MANAGER가 OTP로 assign/replace/release를 확정한다.
5. 서버가 최신 상태를 잠금·재검증하고 재고 원장, allocation, 작업 상태, 감사를 원자 반영한다.
6. 변경된 allocation은 기존 주문의 상품준비중, 포장, 송장, 배송, 반품, 매출 흐름으로 진행한다.

# 제품 결정

| ID | Date | Decision | Status |
|---|---|---|---|
| D-001 | 2026-08-26 | 대상은 판매채널에 이미 존재하는 주문의 고객 변경 요청이다. | confirmed |
| D-002 | 2026-08-26 | 쿠팡 문의·유선 문의·기타는 주문 출처가 아니라 변경 요청 접수 경로다. | confirmed |
| D-003 | 2026-08-26 | 요청받은 특정 PG는 판매 오퍼 조건과 달라도 선택할 수 있다. 그 결과 다른 주문 후보와 매출 통계가 달라지는 것은 정상이다. | confirmed |
| D-004 | 2026-08-26 | 조회는 STAFF 이상, assign/replace/release는 MANAGER 이상과 `CHANNEL_ORDER_MATCHING` OTP를 요구한다. | confirmed |
| D-005 | 2026-08-26 | 배정 해제 후 `PARTIAL/UNMATCHED` 상태로 남기는 것을 허용하며 사유와 명시적 확인을 요구한다. | confirmed |
| D-006 | 2026-08-26 | 변경 후 기존 matching post-cycle과 출고 lifecycle을 계속 사용한다. | confirmed |
| D-007 | 2026-08-26 | 동일 명령은 1회 효과를 보장하고 접수 경로·담당자·사유·before/after를 감사한다. | confirmed |
| D-008 | 2026-08-26 | 판매채널 주문이 없는 독립 출고는 이 메뉴의 비범위이며 재고 수정 메뉴의 `보류` 상태로 처리한다. | confirmed |
| D-010 | 2026-08-26 | 충돌 우선순위는 `이미 시작된 외부 acknowledgement·포장·출력·반품 > 확정 실행된 직원 수동 변경 > 자동 matcher·전체 rematch`로 한다. 같은 등급의 직원 명령은 먼저 커밋한 명령을 우선한다. | confirmed |

# 요구사항과 성공 기준

- R-001 / AC-001: 기존 채널 주문 품목과 수량 슬롯별 allocation을 조회하고 exact PG를 선택한다.
- R-002 / AC-002: 요청 접수 경로와 변경 사유를 필수 기록하고 동일 원문을 allocation provenance와 직원 활동 감사 기록에 보존한다.
- R-003 / AC-003: 오퍼 불일치 PG도 허용하되 preview에서 주문 조건, 선택 PG, 재고·통계 영향을 명확히 표시한다.
- R-004 / AC-004: 교체 성공 시 이전 PG는 `SELLABLE`, 새 PG는 `RESERVED`이며 어느 한쪽만 반영될 수 없다.
- R-005 / AC-005: stale preview, 수량 초과, worker 경합에서는 전체 rollback되고 refresh를 요구한다.
- R-006 / AC-006: STAFF 조회와 MANAGER+OTP mutation 권한이 메뉴와 API에서 일치한다.
- R-007 / AC-007: 변경된 allocation이 기존 주문의 downstream 흐름과 매출 통계에 반영된다.
- R-008 / AC-008: 물리 출고가 이미 진행돼 안전하게 변경할 수 없으면 강제 수정하지 않고 해당 복구 흐름을 안내한다.
- R-009 / AC-009: 판매채널 주문 식별자가 없는 대상은 mutation 0건으로 거부하고 `재고 수정 > 보류`를 안내한다.
- R-010 / AC-010: 동일 idempotency key/payload 재시도는 중복 allocation과 원장 movement를 만들지 않는다.
- R-011 / AC-011: 확정 수동 명령이 활성인 shipment/PG는 아직 시작되지 않은 auto matcher와 전체 rematch가 건너뛰며, 이미 시작된 external/downstream 업무가 있으면 수동 명령이 stable conflict로 중단된다.
