# 다음 버전 개발 상태

사용자는 기존 에이전트에서 `$skip 이거 구현해`처럼 시작합니다. 간편 설치는 Windows Codex를 우선하며 내부 Core는 Linux·Paseo에서도 같습니다. 이 문서는 개발 소스의 상태이며 공개 설치본의 기능 보장이 아닙니다.

## 구현된 경로

- 활성화: 외부 프로젝트 연결, 필요한 현재 파일 근거만 NOW 기록. goal·PRD·tasks·승인 생성 없음.
- 요청: Codex의 현재 실제 사용자 메시지 또는 Paseo의 native 요청을 확인한 후 session goal 생성. 기존 유효한 기록은 canonical resolver로 재사용.
- 위험: goal 맥락과 실제 변경 범위의 source/scope/revision/policy를 따로 검사. 낮은 실패 비용의 가역적 수정은 compact, 업무·재고·권한 등의 영향은 full, 불확실하면 조사.
- 권한: compact의 직접 요청 기반 gate v2와 full의 기존 artifact gate v1 분리. 구현 전 재검증, 취소/철회/범위 변경/미정 결정/오래된 근거는 제한. 모든 gate는 advisory.
- 결과: 원본 요청에 연결한 outcome·검증 surface·미검증 범위 표시. NOW는 구현된 현재 사실만 CAS로 기록.
- Paseo: 기존 기록 뷰어와 별도로 SKIP 작업 패널. 현재 호스트의 실제 workspace에서 같은 Core 실행. 원래 사용자 요청은 서버 메모리에만 유지.
- Windows 패키지: 고정 해시의 Python 동봉, 라이선스와 파일 해시 manifest. 사용자에게 별도 개발 도구 설치를 요구하지 않는 형태로 생성.

## 아직 필요한 수용 증거

Windows 설치기로 개발 패키지를 실제 설치하고 첫 요청·취소·재개·재설치를 확인해야 합니다. Codex local session 형식이 제공되지 않는 호스트는 출처 검증을 통과한 것으로 표시하지 않습니다. 현재 요청 인식은 명시적인 한국어/영어 작업 표현을 보수적으로 처리하며 단독 “응”에서 구현 범위를 만들지 않습니다.

Paseo 서버 통합 테스트는 실제 Core를 subprocess로 실행하지만, 실행 중인 Paseo에 개발 플러그인을 설치한 화면/원격 사용자 수용과는 다릅니다. Windows CI 설정을 작성했다는 사실도 CI 실행 성공을 대신하지 않습니다. 공개 카탈로그·원격 업로드·설치본 교체는 이 개발 작업과 별개입니다.

상세 계약은 [minimal entry](../../references/low-friction-entry-contract.md), 패키지 구조는 [Codex 개발 패키지](../../plugins/codex/README.md)를 참고하세요.

## 개발 검증 결과 (2026-09-09)

- Python: 129개 중 **126개 통과**, Windows 고유 동작 3개는 Linux에서 **NOT_RUN**. 기존 회귀 94개를 포함합니다.
- Paseo: **22개 통과**, TypeScript 검사 통과. 실제 Python subprocess로 활성화 → 요청 → 위험 평가 → compact 허용 → 변경 → 결과 → NOW → 이후 소스 변경 감지를 확인했습니다.
- 패키지: 고정 런타임 SHA-256, 73개 구성 파일의 해시, plugin/skill 구조 검증 통과. 패키지에 들어간 소스 테스트는 Linux에서 33개 중 30개 통과·Windows 전용 3개 미실행입니다.
- 실제 현재 Codex 세션의 마지막 사용자 메시지 ID/본문과 구현 요청 판정을 확인했습니다. 과거 요약으로 goal을 만들지 않았습니다.
- Windows CI 실행·Windows 설치기 검증·Paseo 실제 화면 수용·설치본 전환·원격 업로드: **NOT_RUN**.

개발 ZIP `skip-codex-windows-0.2.0-dev.1.zip`의 SHA-256은 `4ad2721b7904019148699378d57f05bf228bc1e51ae53a4545b4f6b5190488b4`입니다. 이것은 로컬 개발 산출물이며 공개 설치 링크는 아직 발행하지 않았습니다.
