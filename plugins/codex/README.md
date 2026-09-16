# Codex 개발 패키지

이 디렉터리는 Windows용 SKIP Codex 패키지의 소스와 고정 runtime 정보를 담습니다. 패키지는 사용자의 기존 Codex 환경에 SKIP을 추가하기 위한 배포 형식이며 별도의 IDE가 아닙니다.

## 현재 패키지 구성

빌더는 다음 현재 runtime만 패키지에 넣습니다.

- `skip_core`
- `skip_mcp`
- `adapters`
- `schemas`
- MCP App 정적 자산
- `SKILL.md`
- `agents/openai.yaml`
- `references/db-core-contract.md`

퇴역한 file-runtime scripts와 역사적 contract 문서는 런타임 패키지에 포함하지 않습니다.

Windows x64 패키지는 고정 CPython embeddable runtime, 검증한 Python 의존성, 라이선스, 격리된 `_pth`, 파일 hash manifest를 포함합니다. 최종 사용자가 Python, Git, npm, pip, WSL을 따로 설치할 필요는 없습니다.

## 진입점

생성된 패키지는 다음 현재 진입점을 제공합니다.

```text
skip.cmd      → python -m adapters.codex.entry
skip-core.cmd → python -m skip_core.cli
skip-mcp.cmd  → python -m skip_mcp.server
```

`package-manifest.json`의 기본 entrypoint도 `adapters.codex.entry`입니다. 현재 사용자 턴을 검증할 수 없는 host에서는 권한을 만들어내지 말고 capability gap으로 처리합니다.

## 개발 빌드

저장소 루트에서 UI와 의존성을 준비한 뒤:

```bash
python scripts/download_core_dependencies.py
python scripts/build_codex_package.py --output /tmp/skip-windows-dev.zip
```

네트워크 없이 이미 검증할 runtime ZIP을 사용할 때는 `--runtime-zip <path>`를 지정할 수 있습니다. `--with-tests`는 CI용 Core/MCP contract tests를 패키지에 추가합니다.

빌더는 패키지를 **생성만** 합니다. 설치, 업로드, 카탈로그 등록, 활성화는 수행하지 않습니다.

## 검증 경계

CI는 Windows에서 패키지를 만들고 동봉 interpreter를 사용해 Core/MCP의 제한된 contract surface를 실행합니다. 이 결과는 실제 Codex 앱 설치, first-use UX, 화면 수용, 업그레이드/제거, 운영 배포를 증명하지 않습니다.

현재 runtime 계약은 [`../../references/db-core-contract.md`](../../references/db-core-contract.md), CI가 실제로 확인하는 표면은 [`../../docs/ko/verification.md`](../../docs/ko/verification.md)를 참고하세요.