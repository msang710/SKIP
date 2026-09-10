# SQLite 공통 Core 개발본

2026-09-10 개발 구현 후, 사용자 요청에 따라 Linux 로컬 설치본과 Paseo 플러그인을 전환했다. Windows 앱 설치 및 공개 릴리스 검증은 별도다.

SKIP의 업무 기록은 SQLite 한 곳에 저장한다. 설명과 근거는 TEXT, 결정→선택→요구사항→설계→작업→검증 관계는 revision을 포함한 외래 키로 연결한다. CLI·MCP·Paseo는 같은 Application API와 상태 조회를 사용한다. 정상 런타임에는 Markdown 이중 쓰기와 파일 저장소 fallback이 없다. 사용자가 명시적으로 요청한 일회성 이관은 별도 오프라인 유지보수 도구로 수행하며, 원문 바이트·출처·당시 상태를 DB에 보존한다.

## 사용 흐름

1. 연결 시 프로젝트만 활성화한다. 코드나 에이전트 기억에서 goal을 만들어내지 않는다.
2. 실제 사용자의 새 요청이 goal의 출발점이다. 기존 goal의 계속 작업은 명시적으로 연결한다.
3. 현재 소스와 goal/change 위험을 기록한다. 작은 가역 변경은 compact, 불명확하면 조사, 실패 비용이 크면 필요한 결정·설계·검증을 더한다.
4. 사람은 결정 카드에서 추천·이유·위험을 보고 선택한다. 선택만 저장할 수도 있다.
5. 실행은 현재 화면에 연결된 작업 공간·provider·agent·thread가 재확인될 때만 전달한다. 설치된 다른 에이전트나 최근 대화를 검색하지 않는다.
6. 실행 종료와 검증 완료를 분리해 **결과 / 확인 / 남은 일**을 표시한다. 실행 종료 후에도 증거가 없는 필수 검증은 `NOT_RUN`이다.

## 구현 구조

| 영역 | 구현 |
|---|---|
| 저장소 | `skip_core/db.py`, 순서·checksum을 검사하는 4개 migration, 67개 업무 테이블 |
| 공통 명령 | `skip_core/service.py`, `schemas/skip-core-v1.json`, 명령 재시도 receipt와 원자적 변경 |
| 기록 | 불변 revision·seal, head CAS, typed 관계, 명시적 lifecycle |
| 위험·정책 | 8개 실패 영향 차원, goal/change 위험, 소스 snapshot 및 정책 digest |
| 문맥·상태 | `skip_core/queries.py`, goal/stage·출력 budget·페이지 제한, incomplete·STALE 표시 |
| 현재 실행 | `authority.py`, `execution.py`, `delivery.py`, 모델 도구와 분리된 native bridge |
| MCP | `skip_mcp/server.py`, 공식 SDK stdio tools/resources, MCP Apps 결정 화면 |
| 호스트 | `adapters/codex/entry.py`, `plugins/paseo/session-routing.server.ts`, Paseo 현재 agent panel 및 메모리 세션 바인딩 |
| 복구 | 일관된 SQLite backup, 새 경로 restore, 전달 불명 유지, 정확한 host receipt에 의한 정리 |

초안 55개에 설정·명령 receipt·request-goal 관계 4개를 더했고, 이후 승인된 이관을 위해 원문·섹션·링크·구조화된 기록 참조·이관 이력·portable Git identity 6개를 더했다. 당시 승인과 PASS를 현재 실행 권한이나 검증으로 변환하지 않는다. 출처와 문서 처리 상태를 위한 테이블 2개를 더해, 과거 결정·요구사항·설계·작업을 각각 네이티브 기록으로 복원하고 당시 상태와 미확정 참조를 보존한다. 관계의 실제 기준은 `skip_core/migrations/*.sql`이다. 설정 JSON도 DB의 불변 revision 안에 있으며 별도 설정 파일을 업무 원본으로 사용하지 않는다.

## 환경과 호환 범위

| 항목 | 개발 검증 | 실제 호스트 수용 |
|---|---|---|
| Linux SQLite / CLI | 임시 DB에서 CRUD·rollback·동시 CAS·backup/restore 검증 | 로컬 기존 프로젝트 기록 이관·원본 해시 대조 완료 |
| MCP tools/resources | 실제 SDK client의 initialize/list/call/read 검증 | 각 IDE 연결 설정은 호스트마다 필요 |
| Codex 현재 턴 | 실제 형식의 session fixture에서 원 요청·계속 요청·권한 범위 검증 | 현재 앱의 안정적 사용자 event ID 제공 여부 확인 필요 |
| Paseo 현재 대화 전달 | SDK 타입 검사, mock host의 정확한 대상·재전송 금지·턴 상관 관계 검증 | 실제 프로젝트 조회 RPC 통과. 에이전트 메시지 전송·시각적 화면 수용 `NOT_RUN` |
| MCP Apps | 번들·선택 메시지 계약 검증 | 사용자 메시지 전달 capability가 있는 호스트에서만 해당 버튼 사용 |
| Windows | Python·SQLite·MCP 의존성·UI가 포함된 ZIP 생성 | 실제 앱 설치·PATH 없는 실행은 로컬 `NOT_RUN`, CI job 추가 |

MCP의 공통 도구는 조회·제안·결과 기록을 제공한다. MCP 지원 자체가 인간 승인 인증이나 새 턴 시작 지원을 뜻하지 않는다. MCP Apps의 선택 버튼은 현재 대화에 사용자 메시지를 전달하며, 검증 가능한 native adapter가 이를 확인해야 DB 선택으로 저장된다. 지원하지 않는 호스트에는 수행 가능한 행동만 표시한다.

Paseo는 정확한 메시지와 turn ID가 연결된 종료 이벤트만 실행 결과로 기록한다. 공개 SDK의 원자적 idle 조건부 전송·취소·영구 메시지 receipt 조회는 아직 연결하지 않았다. 전송 직전 상태가 바뀌는 경쟁을 호스트 수준에서 완전히 차단한다고 주장하지 않는다. 전달 불명은 재시도하지 않고, 취소 요청은 확인 전까지 완료 처리하지 않는다. receipt 조회가 없는 호스트에서는 불명 상태를 자동 해소하지 않는다.

## 데이터와 권한 경계

DB에는 업무 기록과 불투명한 receipt digest/message key만 남는다. 살아 있는 IDE·workspace·agent·thread·UI handle, 토큰, challenge는 adapter 메모리에만 존재한다. 다른 환경에서는 같은 업무 revision을 새 현재 요청으로 계속할 수 있지만 과거 연결은 복원하지 않는다.

모델 도구에는 승인·전송 권한을 노출하지 않는다. Native adapter의 실제 사용자 입력을 신뢰하는 구조이며, 동일 OS 사용자 권한으로 임의 코드를 실행하는 주체를 격리하는 보안 경계는 아니다. 파일 쓰기를 물리적으로 막지 않는 `advisory` 강제력을 유지한다.

## 개발 및 검증

개발자는 `requirements/core.txt`로 Core/MCP 의존성을 준비하고 `ui/mcp-app`에서 `npm ci`, `npm run build`를 실행한다. 이는 소스 개발 fallback이며 대상 사용자에게 요구하는 설치 흐름이 아니다.

```sh
python -m unittest discover -s tests -t . -p 'test_*.py' -v
npm test --prefix plugins/paseo
npm run typecheck --prefix plugins/paseo
npm test --prefix ui/mcp-app
python scripts/download_core_dependencies.py
python scripts/build_codex_package.py --output dist/skip-core-candidate.zip --with-tests
```

소스 CLI는 `./skip --project <id> query status`, MCP는 `python -m skip_mcp.server --project <id> --workspace <현재 경로>`로 같은 Core를 사용한다. 조회로 DB를 초기화하지 않는다. 활성화는 실제 사용자 입력을 확인하는 native adapter 또는 interactive CLI가 담당한다.

Windows candidate에는 `skip.cmd`, `skip-core.cmd`, `skip-mcp.cmd`와 동봉 Python이 있다. 런타임에 pip/npm 다운로드는 없다. Windows 앱의 실제 설치 접점이 검증되기 전까지 한 번 클릭 설치 완료나 앱 전체 지원을 선언하지 않는다.

구형 파일 기반 scripts·문서·테스트는 이전 세대 검증을 위해 소스에 남아 있지만 새 패키지에 포함되지 않으며 새 활성 진입점에서 호출하지 않는다. 기존 설치본은 이번 변경과 별개다. 실제 전환 때 활성 writer와 장시간 열린 세션까지 함께 확인해야 한다.

Paseo 개발 플러그인은 Core 위치를 `SKIP_CORE_ROOT`, 실행기를 `SKIP_PYTHON`으로 명시할 수 있다. 별도 플러그인 캐시에서 실행할 때 저장소 경로를 추측하지 않고 이 설정으로 같은 Core를 연결한다. 실제 설치 전환 단계에서 이 위치를 고정하고 확인한다.

로컬 합성 성능 기준선: goal 100/1,000/10,000개에서 첫 30개 상태 조회를 각각 10회 측정했다. 중앙값은 0.476/1.135/4.267ms, 최대 1.231/1.545/5.389ms였다. `tools/benchmark_core.py`로 재현할 수 있다. 단순 goal fixture의 warm 조회이며 큰 본문·실제 source 검사·Windows 성능을 보장하지 않는다.

## 이관 이후의 사용

`skip_history`와 `skip_history_record`, CLI의 `history` / `history.record`가 동일한 DB 원문과 관계를 읽는다. Paseo의 **이관된 기록**에서 제목·본문 검색, 목록 더 보기, 긴 본문 나눠 읽기를 지원한다. 역사 기록의 상태는 당시 상태로 표시하며 현재 NOW의 새 증거와 구분한다. 오래 열린 에이전트가 구형 스킬을 계속 사용하지 않도록 새 연결에서 설치 스킬과 MCP를 다시 읽는다.

이관용 `tools/migrate_records.py`는 새 candidate만 생성하고 기존 DB에 덮어쓰지 않는다. Git 내부 파일은 업무 데이터로 취급하지 않으며 비활성 백업에 남긴다. 원본 재대조·FK·무결성 검사를 통과한 뒤에만 활성화한다. 이미 새 DB에 업무 변경이 생겼다면 예전 파일 writer로 복귀하지 말고 DB 백업 및 호환 Core로 복구한다.

### 기존 기록 재이관

기존 원문은 복구 근거로 보존하고, 업무 내용은 일반 목표·결정·요구사항·설계·작업·검증 기록으로 복원한다. UI, CLI, MCP는 같은 `record.list`와 `record`를 조회한다. 원래 상태·시점·식별자와 미확정 연결은 `record_origins`에 연결되며, 별도의 이관용 업무 내용 저장소를 만들지 않는다. `document_dispositions`는 변환·참고·제외 여부를 기록한다.

사용자가 제외한 완료·대체·반려 문서는 기본 업무 목록에서 빠진다. 구현했지만 검증이 남은 기록은 유지한다. 기존에 확정된 제품 결정을 다시 미정 질문으로 만들지 않으며, 당시 검증 결과를 현재 소스의 새 검증으로 승격하지 않는다. 원문에 없는 선택지나 인수 기준은 생성하지 않는다.
