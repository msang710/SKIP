# 설치와 사용

[SKIP](../../README.md) · [철학과 제품 결정](concepts.md) · [구조와 런타임](architecture.md) · [Paseo 플러그인](paseo.md) · [검증과 한계](verification.md)

## 소스 checkout

Linux가 검증된 소스 checkout 환경입니다. Python 3과 Git이 필요하며 Core 런타임은 Python 표준 라이브러리와 SQLite를 사용합니다. 소스 checkout은 별도 호스팅 서비스를 설치하거나 사용자의 IDE를 교체하지 않습니다.

[공식 Codex Skill 문서](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)의 사용자별 `.agents/skills` 경로에 설치합니다. 비어 있는 목적지를 사용하세요.

```bash
mkdir -p "$HOME/.agents/skills"
git clone https://github.com/msang710/SKIP.git "$HOME/.agents/skills/skip"
```

Codex는 Skill 변경을 자동 감지합니다. 나타나지 않으면 재시작하고, 기존 활성 세션이 이전 지침을 사용 중이면 새 작업에서 확인합니다.

### Windows

패키징된 Windows 경로는 SKIP에 포함된 Python/runtime을 사용합니다. 정상적인 패키지 사용을 위해 대상 사용자가 Python, SQLite, npm, Git을 별도로 설치할 필요는 없습니다. Windows 설치기 수용 검증은 패키지 생성과 자동 검사와 별개입니다. [Core 개발 상태](db-core.md)를 확인하세요.

Windows/macOS의 네이티브 소스 실행은 현재 검증 문서에 명시된 경우를 제외하고 검증하지 않았습니다.

## 에이전트 대화에서 사용

현재 Skill ID는 `$skip`입니다.

인자 없이 호출하면 도움말처럼 동작하며 목표를 만들지 않아야 합니다.

```text
$skip --help
```

의미 있는 작업에서는 구현 파일명을 먼저 지정하기보다 원하는 업무 동작과 범위를 설명하세요.

```text
$skip으로 주문 취소 시 재고 예약을 해제하는 흐름을 조사해줘.
포장이 시작된 주문의 예외 처리를 정리하고,
계획을 보여준 뒤 내 승인 전에는 구현하지 마.
```

기존 작업을 재개하는 새 세션은 대화 기억을 프로젝트 상태로 가정하지 말고, 정확한 기존 목표를 지정해 fresh bounded context를 읽어야 합니다.

SKIP MCP 도구가 연결되어 있다면 일반 읽기/쓰기는 MCP를 우선합니다. 대표 도구는 `skip_status`, `skip_context`, `skip_decisions`, `skip_submit`, `skip_amend`, `skip_result`, `skip_learning`, `skip_execution_status`입니다.

## 로컬 CLI와 개발 진입점

설치된 launcher는 로컬 Core와 프로젝트 identity를 해석합니다.

```bash
skip --workspace <project-root> query status
```

소스 개발 시 fallback은 Core module CLI입니다.

```bash
python -m skip_core.cli --project <project-id> query status
python -m skip_core.cli --project <project-id> query context --input '{"goal_id":"<goal-id>"}'
```

Codex native adapter는 provenance 또는 실행 권한 확인이 필요할 때 실제 현재 호스트 발화를 읽습니다.

```bash
python -m adapters.codex.entry --workspace <project-root> --project <project-id> --goal <goal-id>
```

배포 이후에는 퇴역한 `scripts/intent_context.py`나 파일 기반 runtime writer를 사용하지 마세요. 현재 명령과 경계의 권위 있는 문서는 [Core 계약](../../references/db-core-contract.md)입니다.

## 기록과 개인정보

SQLite가 유일한 runtime 업무 기록 저장소입니다.

Linux 기본 데이터 경로는:

```text
~/.local/share/SKIP
```

이며 `$XDG_DATA_HOME`이 있으면 그 아래의 `SKIP`을 사용합니다. 기본 데이터베이스 파일은 `skip.db`입니다. `SKIP_DATA_ROOT`로 명시적인 호스트 데이터 경로를 지정할 수 있습니다.

데이터베이스에는 목표, 결정, 선택, 요구사항, 계획, 작업, 근거, 학습 기록, 설정, provenance, 현재 사실이 typed revision과 관계로 저장됩니다. 제품 소스 코드는 제품 저장소에 남으며, SKIP은 병렬 Markdown/JSON/YAML 업무 저장소나 `NOW` 디렉터리를 운영하지 않습니다.

과거 기록에는 실제 개발 이력이 세밀하게 남을 수 있으므로 공개를 위해 따로 준비하지 않았다면 개인 프로젝트 데이터로 취급하세요. 이관된 과거 자료를 조회해도 새 승인, 현재 소스 근거, 현재 실행 권한이 되지 않습니다.

SKIP 공개 배포판에는 workflow 코드, 문서, 테스트, synthetic example이 포함되며 원본 프로젝트 기록은 포함하지 않습니다. 실제 문서 발췌본은 공개 범위를 검토한 뒤에만 포함하세요. [QuickHack 개발 사례](../../examples/quickhack/README.md)가 그 형식입니다.

## 업데이트와 복구

Core schema upgrade는 명시적으로 수행합니다. 먼저 candidate DB를 업그레이드하고, 새 schema에 오래된 writer를 실행하거나 오류가 났다는 이유로 live DB를 자동 교체하지 않습니다.

`Database.backup`은 SQLite backup API를 사용하고 무결성을 확인합니다. restore는 기존 DB를 덮어쓰거나 자동 활성화하지 않고 새 파일에 복구를 연습합니다. 현재 복구 동작은 [Core 개발 상태](db-core.md)와 [Core 계약](../../references/db-core-contract.md)을 확인하세요.
