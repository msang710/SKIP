# Verification and limits

[SKIP](../../README.en.md) · [Concepts and decisions](concepts.md) · [Architecture and runtime](architecture.md) · [Installation and usage](usage.md) · [Paseo plugin](paseo.md)

## Automated CI surfaces

GitHub Actions runs on pushes to `main`, pull requests, and manual dispatch. The current workflow separates the following evidence surfaces:

### Python / Core

Ubuntu 24.04 with Python 3.14 and Node.js 24:

```bash
npm ci --prefix ui/mcp-app --ignore-scripts --no-audit --no-fund
npm run build --prefix ui/mcp-app
npm test --prefix ui/mcp-app
python -m pip install -r requirements/core.txt -r requirements/maintenance.txt
python -m unittest discover -s tests -t . -p 'test_*.py' -v
```

CI also runs the retained legacy Python regression suite. Those tests protect migration/regression behavior; they are **not current runtime documentation** and do not make retired file-runtime entry points supported interfaces.

### Paseo

On Ubuntu 24.04 / Node.js 24, CI runs:

```bash
npm ci --prefix plugins/paseo --ignore-scripts --no-audit --no-fund
npm test --prefix plugins/paseo
npm run typecheck --prefix plugins/paseo
```

A separate compatibility job compiles the plugin against the supported Paseo 0.8 SDK line.

### Windows bundled Core

On Windows Server 2025, CI builds the pinned Windows package, expands it, clears `PATH`, and runs Core/MCP contract tests through the **bundled Python interpreter**. This verifies package construction and a bounded bundled-runtime surface; it is not the same as installing SKIP into a real desktop host.

## What CI does not prove

Passing CI does **not** establish:

- live Codex/Paseo host acceptance,
- installer UX or upgrade behavior,
- GUI/visual acceptance,
- physical device behavior,
- production deployment or operational safety,
- arbitrary host-write interception,
- same-OS-user security isolation.

Evidence must stay attached to the surface that produced it. Source tests do not become GUI evidence; package construction does not become installation evidence; a successful execution does not imply every required verification passed.

## Current runtime authority

Use [references/db-core-contract.md](../../references/db-core-contract.md) for the current runtime contract and [Shared SQLite Core](db-core.md) for the public overview. Retired scripts may remain in the source tree for regression/migration coverage, but their historical interfaces are not current runtime instructions.