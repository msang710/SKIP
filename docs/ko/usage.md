# 설치와 사용

[SKIP](../../README.md) · [철학과 제품 결정](concepts.md) · [구조와 런타임](architecture.md) · [Paseo 플러그인](paseo.md) · [검증과 한계](verification.md)

## 설치

로컬 Skill 사용을 위한 소스 checkout입니다. daemon·호스트 adapter·Python 패키지를 설치하지 않습니다. backend는 Python 표준 라이브러리를 사용하고, 터미널 UI는 `curses`, 선택적 호스트 캐시는 POSIX 파일시스템 기능을 사용합니다. Linux에서 검증했으며 네이티브 Windows/macOS 실행은 검증하지 않았습니다.

[공식 Codex Skill 문서](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills)의 사용자별 `.agents/skills` 경로에 설치합니다. 이미 설치된 경로를 덮어쓰는 명령은 아니므로 비어 있는 목적지를 사용합니다.

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\.agents\skills" | Out-Null
gh repo clone msang710/SKIP "$HOME\.agents\skills\skip"
```

### macOS / Linux

```bash
mkdir -p "$HOME/.agents/skills"
gh repo clone msang710/SKIP "$HOME/.agents/skills/skip"
```

필요하면 먼저 GitHub CLI를 인증합니다.

```bash
gh auth login
```

Codex는 Skill 변경을 자동 감지합니다. 나타나지 않으면 재시작하고, 기존 작업이 이전 지침을 사용 중이면 새 작업에서 확인합니다. [공식 안내](https://learn.chatgpt.com/docs/build-skills).

## 사용

현재 Skill ID는 `$skip`입니다.

인자 없이 호출하면 `--help`와 동일하게 동작하며 부작용이 없습니다.

```text
$skip으로 이 기능을 조사하고, 계획을 먼저 보여준 뒤 승인 전에는 구현하지 마.
```

주요 컨텍스트 선택 옵션:

```text
$skip --now
$skip --YYMMDD
$skip --date <date>
$skip --goal <goal>
$skip --artifacts <artifact>
$skip --focus decisions
$skip --decision <decision>
$skip --verify
$skip --compare ...
$skip --setup
```

현재 옵션은 `$skip --help`에서 확인할 수 있습니다.

## 기록

Linux 기본 경로는 `~/.local/share/SKIP`이며 `$XDG_DATA_HOME`이 있으면 그 아래의 `SKIP`을 사용합니다. macOS/Windows 기본값과 로컬 프로젝트 registry는 [record-store contract](../../references/record-store-contract.md)에 정의되어 있습니다. `--record-root` 또는 `INTENT_TO_CODE_RECORD_ROOT`로 저장소를 명시할 수 있습니다.

프로젝트를 조회하는 backend 명령에는 기존 기록 프로젝트가 필요합니다. 해당 메타데이터가 있는 `--project`를 지정하거나 workspace identity를 등록해야 합니다. `--project` 자체는 프로젝트를 생성·등록하지 않으며, 이 소스에는 개인 기록 저장소가 포함되어 있지 않습니다.

과거 산출물은 다음 구조에 저장합니다.

```text
<record-root>/projects/<project-id>/features/<goal-slug>/
```

현재 상태 기록은 다음 위치에 둡니다.

```text
<record-root>/projects/<project-id>/NOW/
```

Record store에는 실제 개발 이력이 세밀하게 남을 수 있으므로, 공개를 목적으로 따로 준비하지 않았다면 **개인 프로젝트 데이터로 취급해야 합니다.**

SKIP의 공개 배포판에는 workflow, retrieval logic, 문서, 테스트, synthetic example을 포함합니다. **원본 프로젝트 기록은 비공개로 유지합니다.** 실제 문서 발췌본은 공개할 범위를 선택하고 검토한 뒤 포함할 수 있습니다. [QuickHack 개발 사례](../../examples/quickhack/README.md)가 그 형식입니다.
