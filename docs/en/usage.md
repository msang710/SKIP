# Installation and usage

[SKIP](../../README.en.md) · [Concepts and decisions](concepts.md) · [Architecture and runtime](architecture.md) · [Paseo plugin](paseo.md) · [Verification and limits](verification.md)

## Install

This is a source checkout for local skill use. It does not install a daemon, a host adapter, or Python packages. The backend uses Python's standard library; the terminal setup UI imports `curses`, and the optional host cache uses POSIX filesystem operations. Linux is the verified environment; native Windows/macOS execution has not been qualified.

Install into the per-user `.agents/skills` directory described in the [official Codex skill documentation](https://learn.chatgpt.com/docs/build-skills#where-codex-loads-local-skills). Use an unused destination; cloning does not overwrite an existing skill checkout.

### Windows PowerShell

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\.agents\skills" | Out-Null
gh repo clone msang710/SKIP "$HOME\.agents\skills\skip"
```

### macOS / Linux

```bash
mkdir -p "$HOME/.agents/skills"
gh repo clone msang710/SKIP "$HOME/.agents/skills/skip"
```

Authenticate first when needed:

```bash
gh auth login
```

Codex detects skill changes automatically; restart it if the skill does not appear. Existing active sessions may still need a fresh task to use the updated instructions. [Official skill discovery guidance](https://learn.chatgpt.com/docs/build-skills).

## Use

The current skill identifier is `$skip`.

With no arguments it behaves like `--help` and is side-effect free.

```text
Use $skip to investigate this feature, show the plan first, and do not implement before approval.
```

Common context selectors:

```text
$skip --now
$skip --YYMMDD
$skip --date <date>
$skip --goal <goal>
$skip --artifacts <artifact>
$skip --focus decisions
$skip --decision <decision>
$skip --verify
$skip --compare ...
```

Use `$skip --help` for the current option reference.

## Records

The Linux default is `~/.local/share/SKIP` (or `$XDG_DATA_HOME/SKIP`). macOS and Windows defaults and the local project registry are documented in the [record-store contract](../../references/record-store-contract.md). `--record-root` and `INTENT_TO_CODE_RECORD_ROOT` can select an explicit store.

A record project must already exist for backend commands that resolve it. Use an explicit `--project` with that project's metadata or a registered workspace identity. `--project` does not create or register a project. The repository ships no personal record store.

Historical artifacts are stored under:

```text
<record-root>/projects/<project-id>/features/<goal-slug>/
```

Current-state records live under:

```text
<record-root>/projects/<project-id>/NOW/
```

The record store may contain detailed development history and should be treated as private project data unless deliberately prepared for publication.

A public distribution of SKIP ships workflow code, documentation, tests, and synthetic examples. Original project records stay private. Real-document excerpts may be published only after selecting and reviewing their disclosure scope, as in the [QuickHack case study](../../examples/quickhack/README.md).
