# External record store contract

## Root resolution

Resolve the record root in this order:

1. explicit selector `--record-root` used by the agent tooling
2. `INTENT_TO_CODE_RECORD_ROOT`
3. platform data default

Never use a repository-local `records/` directory beside the installed or development Skill as runtime records. A selected root is exclusive for the invocation: never merge projects or zero-match results from lower-priority roots. The selector manifest reports `record_root_source` as `explicit`, `environment`, or `platform-default`.

Defaults:

- Linux: `$XDG_DATA_HOME/SKIP`, otherwise `~/.local/share/SKIP`
- macOS: `~/Library/Application Support/SKIP`
- Windows: `%LOCALAPPDATA%\SKIP`

The root may itself be a separately managed private Git repository. Do not initialize, commit, pull, push, move, or delete a record repository without explicit authorization.

## Layout

```text
<record-root>/
└── projects/
    └── <project-id>/
        ├── project.yaml
        ├── NOW/
        └── features/
```

Use lowercase letters, digits, and hyphens for `project-id` and goal slugs. Resolve and validate every target beneath the record root. Reject `..`, absolute record subpaths, and symlink escape.

## Project identity

Keep portable identity and source composition in `project.yaml`:

```yaml
version: 2
project_id: example-project
display_name: Example Project
workspace:
  source_root: .
sources:
  workspace:
    kind: workspace
    source_root: .
  primary:
    kind: git
    source_root: config
    repository:
      identities:
        - github.com/example/project
record_contract:
  historical_root: features
  current_root: NOW
created: YYYY-MM-DD
updated: YYYY-MM-DD
```

`workspace.source_root` is the portable logical project boundary. Each source root is relative to that boundary and may represent a Git repository or non-Git workspace content. Normalize Git identities by removing credentials, scheme, trailing slash, and `.git`. Never persist embedded credentials.

## Local registry

Store machine-specific workspace mappings outside both product and portable record repositories:

- Linux: `$XDG_CONFIG_HOME/intent-to-code/workspaces.yaml`, otherwise `~/.config/intent-to-code/workspaces.yaml`
- macOS: `~/Library/Application Support/intent-to-code/workspaces.yaml`
- Windows: `%APPDATA%\intent-to-code\workspaces.yaml`

Use registry version 2 for new entries:

```yaml
version: 2
bindings:
  paseo:
    prj_0123456789abcdef: example-project
projects:
  example-project:
    sources:
      workspace:
        source_root: .
      primary:
        source_root: config
        repository_identity: github.com/example/project
```

Resolve a project using explicit project ID, registered runtime identity, legacy exact registered workspace root, then normalized Git identity. A provider hook supplies only runtime context and must not own a second project-alias registry. A directory basename is diagnostic only and never sufficient when multiple candidates exist.

The selector may discover a Paseo `projectId` through `PASEO_PROJECT_ID` or, when launched by Paseo, through the read-only `paseo project ls --json` contract using `PASEO_CLI`. Match the exact project path first and otherwise the nearest containing project root. If a runtime ID is unavailable or was reissued, validate only explicitly declared relative source roots against their Git identities; never recursively choose the first nested repository. Reject source-root escapes, equal-specificity ambiguity, and conflict with a registered Git identity.

Do not create or modify registry entries without user authorization. Stop on conflicting workspace and repository identities.

## Product repository boundary

Do not create SKIP artifacts, profiles, registry files, or NOW records in the product repository by default. Repository `AGENTS.md` remains applicable guidance but does not change record ownership.

For a record concerning one source, declare its source ID/root and use paths relative to that source. When one record spans multiple roots, qualify evidence as `<source-id>:<relative-path>`. Resolve source roots from the current runtime workspace only when inspecting code; do not copy machine-specific absolute paths into portable records.

## Migration

Migrate existing product-local or sibling records non-destructively:

1. identify source and destination roots
2. copy without deleting the source
3. add project identity and portable metadata where necessary
4. compare file inventory and hashes
5. validate selection in the new store
6. switch the registry only after approval
7. remove or relocate old records only under separate explicit approval
