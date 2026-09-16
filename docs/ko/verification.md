# 검증과 한계

[SKIP](../../README.md) · [철학과 제품 결정](concepts.md) · [구조와 런타임](architecture.md) · [설치와 사용](usage.md) · [Paseo 플러그인](paseo.md)

## 자동 CI 표면

GitHub Actions는 `main` push, pull request, 수동 실행에서 동작합니다. 현재 workflow는 다음 근거 표면을 분리합니다.

### Python / Core

Ubuntu 24.04, Python 3.14, Node.js 24에서:

```bash
npm ci --prefix ui/mcp-app --ignore-scripts --no-audit --no-fund
npm run build --prefix ui/mcp-app
npm test --prefix ui/mcp-app
python -m pip install -r requirements/core.txt -r requirements/maintenance.txt
python -m unittest discover -s tests -t . -p 'test_*.py' -v
```

CI는 보존된 legacy Python regression suite도 실행합니다. 이 테스트는 migration/regression 보호용이며 **현재 runtime 문서가 아닙니다.** 퇴역한 file-runtime 진입점을 현재 지원 인터페이스로 만들지 않습니다.

### Paseo

Ubuntu 24.04 / Node.js 24에서:

```bash
npm ci --prefix plugins/paseo --ignore-scripts --no-audit --no-fund
npm test --prefix plugins/paseo
npm run typecheck --prefix plugins/paseo
```

별도 compatibility job은 지원하는 Paseo 0.8 SDK 계열을 대상으로 plugin compile을 확인합니다.

### Windows bundled Core

Windows Server 2025에서 고정 Windows 패키지를 만들고 압축을 푼 뒤 `PATH`를 비운 상태에서 **동봉 Python interpreter**로 Core/MCP contract test를 실행합니다. 이는 패키지 생성과 제한된 bundled-runtime 표면을 검증하며, 실제 desktop host에 SKIP을 설치하는 사용자 여정과는 다릅니다.

## CI가 증명하지 않는 것

CI 통과만으로 다음을 주장할 수 없습니다.

- 실제 Codex/Paseo host 수용,
- installer UX와 upgrade 동작,
- GUI/시각 수용,
- 물리 장치 동작,
- production 배포·운영 안전성,
- 임의 host write 차단,
- 같은 OS 사용자 보안 격리.

근거는 실제로 확인한 표면에만 연결합니다. source test는 GUI 근거가 아니고, package 생성은 installation 근거가 아니며, 실행 성공은 모든 필수 검증의 통과를 뜻하지 않습니다.

## 현재 runtime 권위

현재 runtime 계약은 [references/db-core-contract.md](../../references/db-core-contract.md), 공개 개요는 [SQLite 공통 Core](db-core.md)를 사용하세요. 퇴역 script가 migration/regression 목적으로 소스 트리에 남아 있더라도 그 역사적 인터페이스는 현재 실행 지침이 아닙니다.