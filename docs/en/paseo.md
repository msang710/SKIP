# Paseo plugin

[SKIP](../../README.en.md) · [Concepts and decisions](concepts.md) · [Architecture and runtime](architecture.md) · [Installation and usage](usage.md) · [Verification and limits](verification.md)

## Paseo plugin

The companion plugin is included at [`plugins/paseo`](../../plugins/paseo). Its manifest ID remains `intent-launcher` to preserve existing installations.

It registers the **SKIP Records** workspace/explorer panel, **Open SKIP Records** command, invocation and record attachment sources, record preview/exact-document attachment, and a goal-scoped Decision Inbox. When direct panel attachment is unavailable, it provides a portable `$skip` caller. The invocation parser validates SKIP options; it is part of this plugin's `intent.server.ts`.

From the SKIP repository root:

```bash
npm --prefix plugins/paseo ci
npm --prefix plugins/paseo test
npm --prefix plugins/paseo run typecheck
```

The bundled plugin passes **18 tests** and `tsc --noEmit` on Node.js 24.18.1 using its checked-in lockfile. These checks do not establish live GUI behavior.

To install the source on a daemon where trusted plugins have been enabled:

```bash
paseo plugin install /absolute/path/to/SKIP/plugins/paseo
```

Installation and reload are separate operator actions. This plugin runs as trusted daemon-side code and can read the configured record store. No personal records or `node_modules` are bundled.

| Daemon environment | Purpose / default |
|---|---|
| `INTENT_TO_CODE_RECORD_ROOT` | Record root; defaults to `$XDG_DATA_HOME/SKIP` or `~/.local/share/SKIP` |
| `INTENT_TO_CODE_WORKSPACE_REGISTRY` | Paseo-to-record project bindings; defaults to `$XDG_CONFIG_HOME/intent-to-code/workspaces.yaml` or `~/.config/intent-to-code/workspaces.yaml` |
| `SKIP_RUNTIME_SCRIPT` | Python backend for Decision Inbox; defaults to `~/.agents/skills/skip/scripts/intent_context.py` |

The record project and its `bindings.paseo` entry must already exist. Configure overrides in the daemon's environment. The plugin's project resolver currently uses that exact registry binding; it does not implement every fallback provided by the Python selector. New `prepare/report` UI integration and host write interception are not included. Type declarations support local checks; Paseo supplies the plugin SDK at runtime. Desktop/mobile GUI acceptance requires a separate host check after installation.
