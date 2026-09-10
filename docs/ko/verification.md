# 검증과 한계

[SKIP](../../README.md) · [철학과 제품 결정](concepts.md) · [구조와 런타임](architecture.md) · [설치와 사용](usage.md) · [Paseo 플러그인](paseo.md)

## 검증

[GitHub Actions](https://github.com/msang710/SKIP/actions/workflows/ci.yml)에서 `main` push와 pull request마다 Python 테스트, Paseo 플러그인 테스트, TypeScript 검사를 실행합니다. CI 환경은 Ubuntu, Python 3.14, Node.js 24이며 실제 호스트 연동이나 GUI 동작 검증은 포함하지 않습니다.

현재 소스는 **Linux / Python 3.14.7**에서 검증했습니다. 저장소 루트에서 실행합니다.

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  scripts.test_intent_context scripts.test_decision_runtime scripts.test_decision_runtime_store \
  scripts.test_workflow_runtime scripts.test_context_session scripts.test_workflow_report
```

전체 **94개 테스트**는 기존 selector/context/gate 회귀와 승인 재사용·만료·철회, 소스 변경, 보고 근거, 캐시 격리·손상·동시 쓰기를 포함합니다.

문서 4개를 사용하는 synthetic fixture에서는 cold 본문 파싱 4회, warm 재파싱 0회에 같은 문서 Context Pack을 반환했습니다. 두 호출 모두 현재 gate와 원본 해시를 다시 확인했습니다. 일반적인 속도·토큰 절감률을 입증한 것은 아니며, 실제 호스트 대화 품질·GUI·쓰기 차단은 별도로 검증해야 합니다.
