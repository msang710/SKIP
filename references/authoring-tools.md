# 기록 제출

MCP는 연결된 `skip_submit`, `skip_amend`, `skip_result`를 우선 사용한다. 도구 입력 스키마에 기록 종류별 필드가 노출된다. 별도 Python 스크립트나 SQL을 작성할 필요가 없다. Markdown은 설명 문자열 안에서 그대로 쓴다.

## 공통 기준과 응답

`skip_context(goal_id, request_id)`의 `authoring_base`를 재사용한다. 이것은 명시된 목표와 실제 요청의 연결이며 승인 토큰이 아니다. goal이나 request를 추측해서 생성하지 않는다.

`submission_id`는 한 제출의 재시도 키다. 응답이 유실되면 같은 연결/receipt scope에서 **같은 키와 같은 입력**으로 재시도한다. 내용을 고치면 새 키를 쓴다. 재접속하는 클라이언트는 기존 `--receipt-scope`를 유지한다. 이 값은 사용자 권한을 부여하지 않는다.

성공 응답의 `data.records`에는 저장된 ID, revision, digest, 설명과 연결이 모두 있다. 자기 쓰기를 확인하려고 다시 조회하지 않는다. 실행 전 최신 선택 확인은 별개다. 제출은 최대 64개, 입력은 512KB 이하이며 전부 저장되거나 전부 취소된다. 기록 응답이 128KB를 넘으면 complete=false와 정확한 ID/revision/digest를 반환한다. 이때 필요한 본문만 record 조회로 확장한다. Core 오류의 `details.input_path`는 실패한 제출 항목을 가리킨다.

## 설계와 작업을 한 번에 제출

다음은 `skip_submit`의 `base`, `records` 입력이다. MCP에서는 `submission_id`를 함께 전달한다.

```json
{
  "base": {"goal_id": "<context goal_id>", "request_id": "<context request_id>"},
  "records": [
    {
      "client_ref": "design",
      "kind": "plan",
      "fields": {
        "title": "기록 일괄 제출",
        "design_body": "설계와 작업 연결을 하나의 트랜잭션으로 저장한다.",
        "scope_description": "개발본 Core와 도구",
        "alternatives_body": "개별 제출은 중간 실패 시 일부만 남는다.",
        "rollback_body": "실패 시 전체 롤백"
      },
      "children": {
        "items": [
          {"item_id": "atomic", "title": "원자적 저장", "design_body": "기존 검증을 재사용한다.", "verification_body": "중간 오류 시 전체 취소"}
        ]
      }
    },
    {
      "client_ref": "implementation",
      "kind": "work_item",
      "fields": {
        "operation": "implement",
        "title": "일괄 저장 구현",
        "instruction_body": "Core에 일괄 저장 경로를 추가한다.",
        "completion_definition": "롤백과 재시도 검증 통과",
        "workflow_depth": "compact"
      },
      "children": {
        "plan_items": [{"plan_id": "$design", "plan_item_id": "atomic", "rationale": "해당 설계 구현"}],
        "checks": [{"description": "중간 실패 원자성 테스트", "surface": "unit", "required": 1}]
      }
    }
  ]
}
```

`$client_ref`는 같은 제출 안에서 **앞에 있는** 기록을 가리키며 ID와 revision을 Core가 채운다. 의존 작업을 먼저 놓는다. 기존 기록은 정확한 ID와 revision을 적는다. option/criterion/check/item ID와 position은 생략하면 생성된다. 다른 작업에서 참조할 plan item에는 예시처럼 짧은 item_id를 정한다. work의 request_id는 base에서 가져온다. 제출은 선택·승인·실행을 만들지 않는다.

CLI fallback도 한 프로세스다. JSON을 stdin으로 보내며 envelope를 조립하지 않는다:

```sh
skip --project <project> --receipt-scope <client> submit --submission-id <unique-id> < payload.json
```

이 파일은 임시 전송용이며 별도 업무 기록 저장소가 아니다. CLI의 `amend`, `result`도 같은 방식으로 입력한다.

## 필요한 부분만 수정

`skip_amend(base, changes, submission_id)`:

```json
{
  "changes": [{
    "target": {"kind": "plan", "id": "<saved id>", "revision": 1},
    "set_fields": {"design_body": "수정된 설명. 다른 필드는 다시 보내지 않는다."}
  }]
}
```

`upsert_items`는 children 그룹별 완전한 항목 배열이다. 기존 항목의 안정적인 ID를 주면 교체하고, 새 ID면 추가한다. `remove_items`는 그룹별 키만 적는다. 예: `{"items":[{"item_id":"atomic"}]}`. 생략한 필드·항목·연결과 다른 기록은 유지한다. 이미 같은 내용이면 revision을 올리지 않는다.

오래된 target은 STALE이다. 그 target만 갱신해서 차이를 검토한다. 응답의 `affected_records`는 이전 버전을 참조하는 현재 기록을 보여준다. 필요한 연결 수정만 후속 amend로 명시한다. 변경된 설계에 기존 승인이나 작업을 자동으로 다시 연결하지 않는다.

## 검증과 필요한 결과만 한 번에 남기기

`skip_result(base, snapshot_id, evidence, submission_id, execution_id?, now?, failure?)`:

```json
{
  "evidence": {"surface": "unit", "result": "FAIL", "summary": "동시 요청 시 중복 배정 재현", "method": "경합 테스트"},
  "failure": {"classification": "product", "expected": "재고는 한 번만 배정", "conditions": "같은 재고를 두 요청이 동시에 확정"},
  "now": {"source_id": "main", "statement": "중복 배정 결함이 재현되어 수정 필요"}
}
```

현재 소스의 snapshot_id는 `skip_observe`로 얻는다. 실행한 작업의 check 결과는 execution_id와 정확한 check_id를 연결한다. 테스트마다 실패 사례나 교훈을 만들지 않는다. 단순 FAIL은 evidence만 남기고, 재발 방지 가치가 있는 실제 사건에만 failure를 붙인다. 기존 사례는 case_id와 시도한 action을 적는다. PASS를 이용한 복구 기록은 기존 case_id와 action이 필요하다. 의도적 오류 주입은 evidence의 purpose를 injection으로, 사례를 남길 때 classification을 injected로 명시한다.

검증 계층과 결과를 합쳐 부풀리지 않는다. 서로 다른 surface/verdict는 각각 제출한다. NOW는 명시한 사실만 생성하고 NOT_RUN을 현재 사실로 올리지 않는다. 결과 저장은 execution 완료, 사용자 승인, 실제 장비 검증을 대신하지 않는다. 후보 가이드라인·검증 의무의 상세 작성은 기존 learning 도구를 사용한다.
