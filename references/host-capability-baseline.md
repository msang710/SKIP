# Host capability baseline

This matrix describes the source distributed in this repository. It does not certify a user's installed host or an adapter maintained elsewhere.

| Surface | Included behavior | Write interception | SKIP classification | Source evidence |
|---|---|---|---|---|
| Codex skill | Skill instructions and appearance/invocation metadata | No host interceptor bundled | `advisory` | `SKILL.md`, `agents/openai.yaml` |
| Python Decision Runtime | Goal-local approval ledger and current action gates | Evaluates gates; does not intercept host file writes | `advisory` | `scripts/decision_runtime.py` |
| CLI / workflow preparation | Request parsing, selected records, current authorization, next action and reports | No source-write or deployment dispatcher | `advisory` | `scripts/intent_context.py`, `scripts/workflow_runtime.py` |
| Paseo identity discovery | Optional project identity lookup through the configured CLI | No plugin UI, attachment or write interceptor bundled | `advisory` | `scripts/intent_context.py::paseo_project_from_daemon` |
| Other CLI or IDE | Portable Python commands and invocation envelopes | Requires a separately implemented and verified host adapter | `advisory` | `scripts/skip_cli.py`; host behavior is `EVIDENCE_PENDING` |

`host-enforced` means the adapter has fixtures proving that a denied SKIP gate prevents the relevant host write or deploy tool even in permissive modes. It does not mean SKIP controls writes performed outside that host. Composer insertion, a Skill instruction, or a successful approval receipt alone is not enforcement.
