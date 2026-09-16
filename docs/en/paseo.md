# Paseo plugin

[SKIP](../../README.en.md) · [Concepts and decisions](concepts.md) · [Architecture and runtime](architecture.md) · [Installation and usage](usage.md) · [Verification and limits](verification.md)

The optional companion plugin lives at [`plugins/paseo`](../../plugins/paseo). It uses the same SQLite Core as CLI/MCP instead of a separate file-based record store.

## What it exposes

The client registers:

- a workspace SKIP panel,
- a current-agent/current-conversation SKIP panel,
- command-center entries for current state and work in this conversation,
- an attachment source for SKIP invocation/context entry,
- native conversation entry surfaces used by the plugin integration.

The server routes panel/query/user actions through the Core bridge and keeps live session/routing state outside business records.

## Core connection

The plugin starts the current Core bridge with:

```text
python -u -m skip_core.bridge
```

Core-root resolution is:

1. explicit `SKIP_CORE_ROOT`,
2. the current source checkout when `skip_core/bridge.py` is present,
3. `<SKIP_DATA_ROOT>/runtime/current` (or the platform-default SKIP data root).

`SKIP_PYTHON` can select the Python executable used for the bridge. `SKIP_DATA_ROOT` selects the Core data root; the live business database remains the same SQLite `skip.db` used by the rest of SKIP.

The plugin does not use `INTENT_TO_CODE_RECORD_ROOT`, `INTENT_TO_CODE_WORKSPACE_REGISTRY`, or `SKIP_RUNTIME_SCRIPT` as the current Core contract.

## Source development and installation

From the repository root:

```bash
npm ci --prefix plugins/paseo --ignore-scripts --no-audit --no-fund
npm test --prefix plugins/paseo
npm run typecheck --prefix plugins/paseo
```

To install the source into a Paseo daemon where trusted plugins are enabled:

```bash
paseo plugin install /absolute/path/to/SKIP/plugins/paseo
```

Installation, daemon reload, and user-visible acceptance are separate operator actions. The plugin does not bundle personal SKIP records or `node_modules`.

## Trust and validation boundaries

The plugin is trusted daemon-side code and can talk to the local SKIP Core. That does not make SKIP `host-enforced`: arbitrary host writes are not intercepted, and same-OS-user isolation is not claimed.

Automated checks cover plugin tests, TypeScript, and compatibility compilation against the supported Paseo SDK line. They do not establish live desktop/mobile visual acceptance, installed-daemon behavior, interruption semantics, or production deployment.

Current host/session handles remain ephemeral. Generic Core/MCP access does not manufacture a human approval or a verified user turn.

See [Shared SQLite Core](db-core.md) for the common runtime model and [Verification and limits](verification.md) for the current automated surfaces.