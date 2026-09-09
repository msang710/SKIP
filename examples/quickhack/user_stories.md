# QuickHack — user_stories.md 발췌

[사례 안내 / Case study](README.md)

판매채널 주문 변경 요청·PG 수동 매칭의 실제 개발 기록에서 선택한 절입니다. 원문의 제목·ID·본문을 유지했습니다. 다른 절과 frontmatter는 생략했습니다.

These are selected sections from actual development records, retaining the original Korean, headings, and IDs. Omitted sections and metadata are not reproduced. This is a documentation copy, not a live approval or operational status record.

---

# US-002 요청과 후보 PG preview

STAFF로서 변경 요청 접수 경로와 사유를 기록하고 특정 PG 선택의 영향을 확인하여 관리자에게 정확한 변경안을 전달하고 싶다.

- 연결 결정: D-002, D-003
- 정상 흐름: 접수 경로, 제한된 사유, exact PG를 입력하고 주문 조건 대비 차이와 재고 영향을 본다.
- 예외: 오퍼 불일치는 경고지만 선택 차단이 아니다. `SELLABLE`이 아니거나 이미 예약된 PG는 차단한다.
- 감사: 입력한 사유 원문은 allocation provenance와 직원 활동 감사 기록에 동일하게 보존한다.

Given 기존 주문과 `SELLABLE` PG가 있을 때, When 사용자가 preview하면, Then 이전/이후 PG, 오퍼 차이, 후보 재고 감소, 허용 여부와 manifest가 반환된다.

# US-003 PG 배정·교체

MANAGER로서 OTP 확인 후 특정 PG를 배정 또는 교체하여 고객 변경 요청을 실제 출고 재고에 반영하고 싶다.

- 연결 결정: D-003, D-004, D-006, D-007
- 정상 흐름: preview manifest, expected revisions, idempotency key, 요청 경로와 사유로 실행한다.
- 수량: 활성 allocation 수는 `matchable_quantity`를 넘지 않는다.
- 부분 실패: 이전 PG release와 새 PG reserve 및 allocation 변경 중 하나라도 실패하면 전체 rollback한다.
- 경합: 자동 worker나 다른 관리자가 먼저 변경하면 0건 처리하고 refresh를 요구한다.
- 중복: 동일 key/payload 재시도는 동일 결과를 반환한다.

Given 유효한 preview와 OTP가 있을 때, When MANAGER가 실행하면, Then 이전 PG와 새 PG의 원장·allocation·work status·감사가 한 transaction으로 확정된다.

# US-005 downstream 안전성

운영자로서 이미 물리 출고가 진행된 주문을 잘못 소급 변경하지 않고 적절한 복구 흐름을 안내받고 싶다.

- 연결 결정: D-006
- 차단: 출력 차수, 활성 포장, 진행 중 외부 쓰기, 송장, 반품, 매출 등 비가역 관계를 서버가 판정한다.
- 복구: 차단 사유와 포장 해제·송장 교체·반품 등 다음 행동을 보여준다.

Given downstream handoff가 시작된 allocation일 때, When preview 또는 execute하면, Then 변화 0건과 안정적인 reason code 및 복구 안내가 반환된다.
