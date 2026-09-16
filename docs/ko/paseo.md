# Paseo 플러그인

[SKIP](../../README.md) · [철학과 제품 결정](concepts.md) · [구조와 런타임](architecture.md) · [설치와 사용](usage.md) · [검증과 한계](verification.md)

선택적으로 함께 쓰는 Paseo 플러그인은 [`plugins/paseo`](../../plugins/paseo)에 있습니다. 별도의 파일 기록 저장소를 쓰지 않고 CLI/MCP와 같은 SQLite Core에 연결합니다.

## 제공하는 표면

클라이언트는 다음을 등록합니다.

- workspace용 SKIP 패널,
- 현재 agent/현재 대화용 SKIP 패널,
- 현재 상태와 이 대화의 작업을 여는 command-center 항목,
- SKIP invocation/context 진입용 attachment source,
- 플러그인 연동에 사용하는 native conversation entry 표면.

서버는 panel/query/user 동작을 Core bridge로 전달하고, 살아 있는 session/routing 상태는 업무 기록 밖에 유지합니다.

## Core 연결

플러그인은 현재 Core bridge를 다음 형태로 실행합니다.

```text
python -u -m skip_core.bridge
```

Core root는 다음 순서로 찾습니다.

1. 명시한 `SKIP_CORE_ROOT`,
2. `skip_core/bridge.py`가 있는 현재 source checkout,
3. `<SKIP_DATA_ROOT>/runtime/current` 또는 플랫폼 기본 SKIP 데이터 루트.

`SKIP_PYTHON`으로 bridge 실행 Python을 지정할 수 있습니다. `SKIP_DATA_ROOT`는 Core 데이터 루트를 선택하며, 업무 기록은 다른 SKIP 인터페이스와 같은 SQLite `skip.db`를 사용합니다.

현재 Core 계약에서는 `INTENT_TO_CODE_RECORD_ROOT`, `INTENT_TO_CODE_WORKSPACE_REGISTRY`, `SKIP_RUNTIME_SCRIPT`를 사용하지 않습니다.

## 소스 개발과 설치

저장소 루트에서:

```bash
npm ci --prefix plugins/paseo --ignore-scripts --no-audit --no-fund
npm test --prefix plugins/paseo
npm run typecheck --prefix plugins/paseo
```

trusted plugin을 허용한 Paseo daemon에 소스를 설치할 때:

```bash
paseo plugin install /absolute/path/to/SKIP/plugins/paseo
```

설치, daemon reload, 실제 화면 수용은 각각 별도의 운영 작업입니다. 플러그인은 개인 SKIP 기록이나 `node_modules`를 번들하지 않습니다.

## 신뢰와 검증 경계

플러그인은 daemon에서 신뢰된 코드로 실행되며 로컬 SKIP Core와 통신할 수 있습니다. 그렇다고 SKIP이 `host-enforced`가 되는 것은 아닙니다. 임의의 host write를 가로채지 않으며 같은 OS 사용자 코드의 격리를 주장하지 않습니다.

자동 검사는 plugin tests, TypeScript, 지원 Paseo SDK 계열과의 compatibility compile을 다룹니다. 실제 desktop/mobile 시각 수용, 설치된 daemon 동작, interruption semantics, production 배포를 증명하지는 않습니다.

현재 host/session handle은 ephemeral입니다. 일반 Core/MCP 접근만으로 인간 승인이나 검증된 사용자 턴을 만들어낼 수 없습니다.

공통 런타임 모델은 [SQLite 공통 Core](db-core.md), 현재 자동 검증 표면은 [검증과 한계](verification.md)를 확인하세요.