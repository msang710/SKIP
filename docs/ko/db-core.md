# SQLite 공통 Core

[SKIP](../../README.md) · [구조와 런타임](architecture.md) · [설치와 사용](usage.md) · [Paseo 플러그인](paseo.md) · [검증과 한계](verification.md)

SKIP의 현재 업무 기록은 **SQLite를 사용하는 Core application API 하나**가 소유합니다. 활성 런타임에는 Markdown/YAML 업무 저장소 fallback이나 이중 writer가 없습니다.

설명은 사람이 읽을 수 있는 텍스트로 보존하고, 목표·결정·선택·요구사항·설계·작업·근거·학습·출처·lifecycle은 revision을 포함한 typed 관계로 연결합니다. CLI·MCP·Codex 연동·Paseo·패키지 진입점은 모두 같은 Core 모델을 사용합니다.

## 런타임 원칙

- 활성화는 프로젝트와 소스를 연결할 뿐, 코드·폴더 이름·에이전트 기억에서 목표를 만들어내지 않습니다.
- 새 목표는 실제 사용자의 현재 요청에서 시작합니다. 기존 작업은 정확한 goal과 최신 bounded context를 읽어 이어갑니다.
- FACT / PRODUCT / DESIGN을 분리합니다. 제품 동작 선택은 사람에게 있고, 기술 설계는 승인 범위 안에서 에이전트에게 맡길 수 있습니다.
- goal/change risk, source snapshot, 현재 record revision, selection, policy, provenance를 기준으로 필요한 workflow 깊이를 정합니다.
- 과거 기록은 지속되는 컨텍스트이지 자동으로 현재 사실·승인·검증이 되지 않습니다.
- 실행 종료와 검증 완료는 별도 상태입니다.
- 전달 결과를 확정할 수 없으면 다른 호스트나 세션에 자동 재전송하지 않습니다.

## 현재 인터페이스

| 표면 | 역할 | 경계 |
|---|---|---|
| `SKILL.md` | 에이전트 호출·작업 규칙 | 지침은 advisory이며 호스트 쓰기를 물리적으로 차단하지 않음 |
| `skip_core` | 트랜잭션, 조회, revision, 권한, 근거, 복구 | 활성 업무 기록의 단일 writer |
| `skip_mcp` | 같은 Core 위의 공식 MCP tools/resources | MCP 접근만으로 인간 승인이 생기지 않음 |
| Codex adapter | 현재 사용자 턴 provenance와 native 실행 진입 | 검증 가능한 현재 host session 필요 |
| Paseo plugin | workspace/current-agent 화면과 native UI 연동 | 살아 있는 routing handle은 adapter 메모리에만 유지 |
| Windows bundle | 고정 Python + Core/MCP/UI/adapter 패키지 | 패키지 생성은 installer/live-host 수용 검증과 별개 |

## 저장과 복구

데이터 루트는 제품 저장소 밖의 플랫폼 로컬 위치를 사용합니다. `SKIP_DATA_ROOT`로 호스트 데이터 루트를 명시할 수 있고 기본 데이터베이스는 `skip.db`입니다.

스키마 업그레이드는 명시적으로 수행합니다. candidate 사본을 먼저 업그레이드·검증한 뒤 별도 승인된 cutover를 해야 합니다. 더 새로운 스키마에 예전 writer를 실행하거나 퇴역한 파일 runtime으로 fallback하지 않습니다.

SQLite backup API와 무결성 검사를 사용합니다. restore는 새 파일에 복구를 연습하며 기존 활성 DB를 몰래 덮어쓰거나 교체하지 않습니다.

과거 기록 이관은 별도 maintenance 작업입니다. 원문 바이트·텍스트·관계·당시 상태·출처를 보존할 수 있지만, 이관된 기록이 새 승인·선택·실행 권한·현재 소스 근거를 얻지는 않습니다.

## 검증 경계

자동 검증은 Core 테스트, MCP protocol, UI/package 생성, Paseo TypeScript/plugin 검사, Windows bundled runtime 검사를 **실제 host·installer·GUI·device·production 수용 검증과 구분**합니다.

CI 통과는 CI가 실제로 실행한 표면에 대해서만 근거가 됩니다. 일반 MCP 지원은 사용자 승인을 인증하거나 현재 host turn을 만들지 않습니다. 강제력은 계속 `advisory`이며 같은 OS 사용자 코드의 격리나 임의 host write 차단을 주장하지 않습니다.

정확한 현재 런타임 계약은 [references/db-core-contract.md](../../references/db-core-contract.md), 현재 CI 표면과 명령은 [검증과 한계](verification.md)를 확인하세요.