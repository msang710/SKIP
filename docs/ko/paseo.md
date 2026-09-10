# Paseo 플러그인

[SKIP](../../README.md) · [철학과 제품 결정](concepts.md) · [구조와 런타임](architecture.md) · [설치와 사용](usage.md) · [검증과 한계](verification.md)

## Paseo 플러그인

함께 사용하는 플러그인 소스는 [`plugins/paseo`](../../plugins/paseo)에 포함되어 있습니다. 기존 설치를 유지하기 위해 manifest ID는 `intent-launcher`를 사용합니다.

**SKIP Records** workspace/explorer 패널, **Open SKIP Records** 명령, 호출·기록 첨부 source, 기록 미리보기·정확한 문서 첨부, 목표별 Decision Inbox를 등록합니다. 패널의 직접 첨부 기능이 없으면 `$skip` 호출문으로 대체합니다. SKIP 옵션을 검증하는 호출 파서는 플러그인의 `intent.server.ts`에 들어 있습니다.

SKIP 저장소 루트에서 의존성과 소스를 확인합니다.

```bash
npm --prefix plugins/paseo ci
npm --prefix plugins/paseo test
npm --prefix plugins/paseo run typecheck
```

포함된 lockfile로 설치한 Node.js 24.18.1 환경에서 플러그인 **18개 테스트**와 `tsc --noEmit`이 통과했습니다. 이는 실제 GUI 동작의 검증과는 별개입니다.

신뢰된 플러그인 기능을 켠 daemon에 설치할 때는 다음 경로를 지정합니다.

```bash
paseo plugin install /absolute/path/to/SKIP/plugins/paseo
```

설치·재로드는 별도의 운영 작업입니다. 플러그인은 daemon에서 신뢰된 코드로 실행되며 설정한 기록 저장소를 읽습니다. 개인 기록과 `node_modules`는 포함하지 않습니다.

| Daemon 환경 변수 | 용도 / 기본값 |
|---|---|
| `INTENT_TO_CODE_RECORD_ROOT` | 기록 루트; `$XDG_DATA_HOME/SKIP` 또는 `~/.local/share/SKIP` |
| `INTENT_TO_CODE_WORKSPACE_REGISTRY` | Paseo 프로젝트 연결; `$XDG_CONFIG_HOME/intent-to-code/workspaces.yaml` 또는 `~/.config/intent-to-code/workspaces.yaml` |
| `SKIP_RUNTIME_SCRIPT` | Decision Inbox용 Python backend; `~/.agents/skills/skip/scripts/intent_context.py` |

기록 프로젝트와 `bindings.paseo` 연결이 먼저 있어야 하며 override는 daemon의 환경에 설정합니다. 현재 플러그인의 프로젝트 식별은 이 정확한 registry 연결을 사용하며 Python selector의 모든 fallback을 제공하지 않습니다. 새 prepare/report의 UI 연결과 호스트 쓰기 차단은 포함하지 않습니다. 타입 선언은 로컬 검사 용도이고 실행 시 SDK는 Paseo가 제공합니다. 설치 후 desktop/mobile GUI 확인은 별도 검증입니다.
