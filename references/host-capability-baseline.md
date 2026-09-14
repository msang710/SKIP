# Host capability baseline

This matrix describes the source distributed in this repository. It does not certify a user's installed host or an adapter maintained elsewhere.

| Surface | Included behavior | Write interception | SKIP classification | Source evidence |
|---|---|---|---|---|
| Codex skill | Skill instructions and appearance/invocation metadata | No host interceptor bundled | `advisory` | `SKILL.md`, `agents/openai.yaml` |
| Python Decision Runtime | Goal-local approval ledger and current action gates | Evaluates gates; does not intercept host file writes | `advisory` | `scripts/decision_runtime.py` |
| CLI / workflow preparation | Request parsing, selected records, current authorization, next action and reports | No source-write or deployment dispatcher | `advisory` | `scripts/intent_context.py`, `scripts/workflow_runtime.py` |
| Paseo companion plugin | Records panel, invocation/record attachment sources, exact-document preview/attachment and Decision Inbox | Plugin source is bundled; no host write interceptor | `advisory` | `plugins/paseo/index.client.tsx`, `plugins/paseo/index.server.ts`, `plugins/paseo/server/` |
| Paseo CLI identity discovery | Optional project identity lookup through the configured CLI | Identity lookup only | `advisory` | `scripts/intent_context.py::paseo_project_from_daemon` |
| Other CLI or IDE | Portable Python commands and invocation envelopes | Requires a separately implemented and verified host adapter | `advisory` | `scripts/skip_cli.py`; host behavior is `EVIDENCE_PENDING` |

`host-enforced` means the adapter has fixtures proving that a denied SKIP gate prevents the relevant host write or deploy tool even in permissive modes. It does not mean SKIP controls writes performed outside that host. Composer insertion, a Skill instruction, or a successful approval receipt alone is not enforcement.

Paseo plugin development targets 0.8.x (`requirements.paseo: >=0.8.0 <0.9.0`). Client/server entries and runtime imports are validated with the published 0.8 SDK and compiler. Older 0.7 hosts must keep their existing release until a coordinated host/plugin update. Core DB schema upgrades are separate. The public 0.8 panel props do not expose addComposerAttachment: exact-record caller copying remains the panel fallback; composer attachment search is registered via the official client API.
