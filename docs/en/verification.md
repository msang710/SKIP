# Verification and limits

[SKIP](../../README.en.md) · [Concepts and decisions](concepts.md) · [Architecture and runtime](architecture.md) · [Installation and usage](usage.md) · [Paseo plugin](paseo.md)

## Verification

[GitHub Actions](https://github.com/msang710/SKIP/actions/workflows/ci.yml) runs Python tests, Paseo plugin tests, and TypeScript checks on pushes to `main` and pull requests. CI uses Ubuntu, Python 3.14, and Node.js 24. It does not verify live host integration or GUI behavior.

The current source was checked on **Linux with Python 3.14.7**. Run the suite from the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest \
  scripts.test_intent_context scripts.test_decision_runtime scripts.test_decision_runtime_store \
  scripts.test_workflow_runtime scripts.test_context_session scripts.test_workflow_report
```

The suite contains **94 tests**, including approval reuse/staleness, revoked goals, bounded selection, source changes, report evidence, and cache isolation/corruption/concurrent writes. The original selection/context/gate tests remain in the suite.

In a synthetic four-document fixture, cold parsing handled four documents and a warm call reparsed none while producing the same document Context Pack. Both calls still evaluated current gates and read original hashes. This is not a general speed or token-saving benchmark. Real-host conversation quality, GUI acceptance and pre-write enforcement require separate evidence.
