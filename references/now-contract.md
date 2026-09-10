# NOW current-state contract

## Purpose and authority

Maintain `NOW` as a compact, replaceable view of the currently implemented system. Use it to route agents quickly; do not treat it as proof independent of current code and observed execution.

Authority order:

1. observed execution
2. tests, schemas, migrations, and configuration
3. source code
4. NOW records
5. historical design records

Record conflicts and repair affected NOW claims. Use `INFERENCE`, `GAP`, or `EVIDENCE_PENDING` when code cannot prove a physical or external environment result.

## Available layout

NOW is the minimum business record. This layout is not a required bundle: create only a useful, verified current-state file. Installation never requires empty index/system/validation/goal files.

```text
NOW/
├── index.md
├── system.md
├── validation.md
└── goals/
    └── <goal-slug>.md
```

Create a goal document once when a new implemented capability first requires one. Subsequent work replaces affected current-state sections instead of adding per-implementation documents.

## Metadata

For a record whose evidence belongs to one source:

```yaml
---
kind: now
project_id: <project-id>
scope: <system | validation | index | goal-slug>
status: <current | partially-verified | stale>
verified_revision: <commit | uncommitted | unversioned>
verified_at: <YYYY-MM-DD>
source_id: <declared-source-id>
source_root: .
---
```

For a record spanning more than one source, replace the single revision/root pair with a revision vector:

```yaml
verified_sources:
  shell:
    source_root: config
    revision: <commit | uncommitted>
  workspace:
    source_root: .
    revision: <unversioned | content-digest>
```

Every source root is relative to the portable logical workspace. Evidence paths are relative to the declared source, or qualified as `<source-id>:<relative-path>` when a record spans sources.

## Content

Record only:

- currently observable behavior
- source entry points and symbols
- product behavior reflected in code
- current data, API, permission, integration, deployment, and recovery contracts
- validation results for the stated revision
- current verified limitations and gaps
- an evidence map linking claims to relative paths, symbols, tests, or commands

Exclude plans, unimplemented approved decisions, rejected alternatives, chronological change logs, conversation summaries, obsolete behavior, and generic next steps.

## Freshness

Compare each applicable `verified_revision` or `verified_sources` revision with the current source state and relevant changed paths.

- no relevant changes: retain `current`
- relevant changes verified and reflected: rewrite affected sections and retain `current`
- relevant changes only partly verified: set `partially-verified`
- known conflict or unassessed relevant change: set `stale`

A revision mismatch alone does not prove staleness. An unavailable revision or dirty relevant path prevents an unconditional `current` claim.

## Refresh after implementation

After approved implementation:

1. run proportionate validation
2. identify affected NOW claims from changed source paths and behavior
3. preserve unrelated concurrent record changes
4. replace superseded current-state text and remove obsolete claims
5. update evidence, revision, date, and status
6. report `PASS`, `FAIL`, `NOT_RUN(reason=...)`, or `EVIDENCE_PENDING`

Do not record successful implementation after failed validation. When only part of the behavior is verified, update the supported facts and mark the remainder explicitly.

Historical records and Git history preserve the past; NOW does not.
