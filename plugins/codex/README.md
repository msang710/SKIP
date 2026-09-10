# Codex 개발 패키지

한국어 기본 진입과 동일 Python Core를 담는 배포 템플릿입니다. `skip/.codex-plugin/plugin.json`은 소스이며 `skills/skip` 내용은 루트 SKILL·references·scripts에서 빌드 시 생성합니다. 수동 복사본을 관리하지 않습니다.

Windows x64 패키지에는 Python 3.14.7 embeddable runtime, Python 라이선스, SKIP GPL 라이선스, 격리된 `_pth`, 실행 경로 및 파일 해시 manifest가 포함됩니다. 런타임 URL과 SHA-256은 [Python 공식 배포 정보](https://www.python.org/downloads/release/python-3147/)에 고정되어 있습니다. 최종 사용자에게 Python/Git/npm/WSL 설치를 요구하지 않습니다.

개발자 빌드:

```bash
python3 scripts/build_codex_package.py --output /tmp/skip-windows-dev.zip
```

네트워크 없이 재빌드하려면 `--runtime-zip <검증 대상 ZIP>`을 사용합니다. `--with-tests`는 CI용 Core 계약 테스트를 추가합니다. 빌더는 설치·업로드·카탈로그 등록을 하지 않습니다.

호스트는 `package-manifest.json`의 executable/arguments를 package root 기준 절대 경로로 실행합니다. 진입 어댑터는 `skills/skip/scripts/codex_entry.py`입니다. 현재 스레드의 실제 사용자 메시지를 확인할 수 없는 호스트는 명시적인 capability gap을 반환합니다. 일반 `intent_context.py entry`는 읽기 전용 진단을 제공합니다.

**현재 검증 경계:** Linux에서 소스 Core·Codex 현재 요청 참조·Paseo 서버 통합과 ZIP 구조를 검사합니다. Windows CI 작업은 동봉 interpreter로 PATH를 비우고 같은 계약을 검사하도록 구성했습니다. Windows 설치기의 실제 설치 흐름, 기존 Codex 호스트의 로컬 session record 제공 여부, 첫 사용자 여정과 화면 수용은 아직 별도 검증이 필요합니다. 로컬 ZIP을 검증된 Windows 설치기로 표시하지 않습니다. 기존 소스/스킬 설치는 동일 Core의 공통 fallback으로 유지합니다.
