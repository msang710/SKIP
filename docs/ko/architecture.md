# 구조와 런타임

[SKIP](../../README.md) · [철학과 제품 결정](concepts.md) · [설치와 사용](usage.md) · [Paseo 플러그인](paseo.md) · [검증과 한계](verification.md)

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
| Paseo 플러그인 | SKIP Records 패널, 호출/기록 첨부 source, 정확한 문서 첨부와 Decision Inbox | `plugins/paseo`에 소스 포함; 별도 Paseo daemon 설정 필요; 쓰기 차단은 없음 |

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

프로젝트 규칙, Context Pack, workflow prepare와 Paseo 플러그인 소스를 포함합니다. clone만으로 플러그인이 설치·재로드되지는 않습니다. 다른 IDE adapter, 플러그인 UI의 새 prepare/report 연결, 호스트 쓰기·배포 차단은 별도 작업이며 현재 강제력은 `advisory`입니다.

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

입력·반환 스키마, 소스 fingerprint의 검증 범위와 호스트 캐시 계약은 [workflow-runtime-contract](../../references/workflow-runtime-contract.md)를 참고하세요.
