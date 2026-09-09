# QuickHack — tasks.md 발췌

[사례 안내 / Case study](README.md)

판매채널 주문 변경 요청·PG 수동 매칭의 실제 개발 기록에서 선택한 절입니다. 원문의 제목·ID·본문을 유지했습니다. 다른 절과 frontmatter는 생략했습니다. 문서에 누적된 여러 수정 단계의 발췌이며, 하나의 시점에 작성된 최초 설계로 해석하지 않습니다.

These are selected sections from actual development records, retaining the original Korean, headings, and IDs. Omitted sections and metadata are not reproduced. This is a documentation copy, not a live approval or operational status record.

---

## T-010A manual intent lease와 결정적 우선순위 검증

- Purpose: D-010의 `downstream > manual > auto/rematch` 우선순위를 DB 실행 결과로 고정한다.
- Dependencies: T-005~T-010.
- Target files or symbols: 신규 manual intent lease model/migration/service; auto matcher/rematch skip predicate; test-only barrier harness; `tests/integration/postgresql/test-manual-order-match-priority-concurrency.mjs`.
- Change: 확정 실행 전 TTL lease를 획득하고 auto/rematch만 이를 존중하게 한다. BM-01~BM-10을 결정적 barrier, 고정 seed 30회, randomized soak 100회로 실행한다.
- Completion conditions: BM-01~06의 winner가 D-010과 일치하고, BM-07~09는 직렬화·stable conflict로 수렴하며, BM-10에서 TTL 이후 자동 흐름이 재개된다.
- Verification: iteration JSON artifact; deadlock 0; retry budget 초과 0; 활성 allocation≤1; balance·work·recovery·downstream 일치; 부분 ledger/audit 0.
- Connected requirements: D-010, R-011/AC-011, CR-006~CR-011.

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

## T-032 — PARTIALLY VERIFIED

- PASS: TypeScript, carrier typecheck, focused ESLint, manual source completion/scope contracts, verification graph, test source layout, Logen label regression, `git diff --check`.
- NOT_RUN: PostgreSQL carrier-state stale/rollback, actual writer concurrency, production build, 실제 UI/OTP.

Review verdict: **NEEDS_WORK** — source 구현은 완료됐지만 실행 환경 검증은 남았다.

Implementation gate: **BLOCKED** — DB/build/UI acceptance 전 운영 rollout 금지.
