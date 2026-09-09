# Context selection contract

## Purpose

Select the smallest deterministic record set before reading content. Run `scripts/intent_context.py select` rather than reimplementing filters in model reasoning.

## Invocation options

| Invocation option | Selector argument | Meaning |
|---|---|---|
| `--help` | `--help` | Show invocation help and exit without selecting context |
| `--setup` | `setup` | Preview effective Core/Project Rules; apply only after exact diff approval |
| `--project ID` | `--project ID` | Select a registered record project |
| `--workspace PATH` | `--workspace PATH` | Resolve or bind the current source workspace |
| `--now` | `--now` | Select current-state records only |
| `--YYMMDD` | `--date 20YY-MM-DD` | Exact artifact `created` date |
| `--date DATE` | `--date DATE` | Exact artifact `created` date |
| `--updated DATE` | `--updated DATE` | Exact artifact `updated` date |
| `--goal SLUG` | `--goal SLUG` | Limit selection to one goal |
| `--artifacts LIST` | `--artifacts LIST` | Limit historical artifact types |
| `--focus decisions` | `--focus decisions` | Prefer decision-bearing records |
| `--decision IDS` | `--decision IDS` | Require decision IDs in selected content |
| `--verify` | `--verify` | Request source freshness checks |
| `--compare` | `--compare` | Allow NOW and historical selection together |
| `--include-undated` | `--include-undated` | Include historical records without `created` |

The agent normalizes prompt shorthand before invoking the selector. Accept only six digits for the shorthand and reject invalid calendar dates.

## Setup behavior

`--setup` is a separate configuration workflow, not a selection filter. Read `project-rules-contract.md`. Preview is side-effect free. The backend writes only with `--apply`, which the agent may invoke only after explicit approval of the displayed diff. Do not combine setup mutation with help, context selection, artifact mutation, or implementation.

```text
python3 scripts/intent_context.py setup --project PROJECT --disable C-010
python3 scripts/intent_context.py setup --project PROJECT --disable C-010 --apply
```

The second form is valid only after approval of the first form's exact change. Writes use atomic replacement and preserve a `.bak` copy when overwriting.

## Help behavior

An explicit skill invocation with no arguments behaves exactly like `--help`.

`--help` takes precedence over every other invocation argument and exits successfully after showing help. It must not resolve a project, access the record store, inspect repository source, create or update records, or enter an approval-gated workflow.

For an explicit skill invocation, respond in the user's language while preserving canonical option names, identifiers, and example values. Include the option table, the `--now` and date conflict rule, and these representative forms:

```text
$skip --now --verify
$skip --date 2026-08-25 --goal feature-name --artifacts prd,user-stories
$skip --now --compare --date 2026-08-25
```

For terminal-oriented help, `scripts/intent_context.py select --help` prints the backend selector reference and exits with status `0` without running selection.

## Selection behavior

Combine filters with `AND`. Apply project, mode, goal, date, artifact, focus, and decision constraints in that order. Sort output paths lexically for repeatability.

Automatic goal routing reads an initialized goal's projection and excludes `revoked` and `superseded` goals. Explicit `--goal` selection and the bounded `history` command may still read them. Legacy goals without a projection retain their existing behavior; selection never creates runtime state.

For an option-free natural-language request, project identity resolution and record selection are separate operations. A provider may apply an exact registered route. When no route matches, it must not inject `--now` or another default record scope; the agent chooses the smallest filters appropriate to the requested workflow stage and then runs the canonical selector. Identity-only resolution returns no documents and is not a completed selection.

`--now` selects `NOW/index.md`, relevant shared NOW documents, and the requested goal document. It does not select `features/` records. `--focus decisions` in NOW mode selects current product behavior rather than unimplemented historical decisions.

Historical date selection reads YAML `created` only. Do not use `updated`, filesystem timestamps, or Git history as a fallback. Exclude missing dates unless `--include-undated` is explicit.

`--now` plus a historical date is invalid unless `--compare` is present. `--compare` returns two explicitly labeled sets.

On zero matches, return `no_match` and read nothing. On ambiguous project identity, path escape, invalid metadata, or conflicting options, return `error` and stop.

## Implicit goal resolution

For an option-free natural-language request, apply this precedence before selection:

1. An explicit `--goal` always wins and skips implicit resolution.
2. Reuse the goal from the most recent successful manifest only when the request clearly continues that work. Keep it conversation-local.
3. Otherwise send the request through stdin to `scripts/intent_context.py goals --stdin` after resolving the project.

The additive `goals` command reads only direct `features/<goal>/` entries, `NOW/goals/*.md`, and at most one routing artifact per goal. It uses existing slug, frontmatter title, and the first goal sentence; it does not use Git history, embeddings, an external model, or a persistent goal index.

`goal-resolution/v1` returns `resolved` with exit `0`, `ambiguous` or `error` with exit `2`, and `no_match` with exit `3`. Only a single deterministic `resolved` result may be passed to canonical `select/context --goal`. For `ambiguous`, report candidates and request a choice. For `no_match`, propose a new slug and scope but do not create records without approval. Never echo or persist the query, guess a candidate, or widen selection.

## Reading discipline

Keep the full selector manifest in structured/detail output. Before expanding selected records, briefly identify project, goal, scope and material selection warnings; normal responses need not print the full manifest. Read selected records in this order when present:

1. `NOW/index.md` or historical `impact.md`
2. requested goal record
3. `prd.md` and `user_stories.md`
4. `system_design.md`
5. `tasks.md`
6. shared `NOW/system.md` and `NOW/validation.md` only when relevant

Do not read unselected records to fill curiosity gaps. If selected records contain a material gap, state the exact additional target and reason before reading it.

### Context Pack compiler

`prepare` composes this canonical selector/compiler with current authorization and next-action selection. See [workflow-runtime-contract.md](workflow-runtime-contract.md). Its document cache does not cache authority or source verification; standalone `context` retains its existing output contract.

After bounded selection, prefer the read-only compiler for the active workflow stage:

```text
python3 scripts/intent_context.py context --project PROJECT --goal GOAL \
  --artifacts prd,system-design,tasks --stage implementation
```

`--stage` is one of `restore`, `impact`, `requirements`, `design`, `tasks`, `implementation`, or `validation`. `--format` accepts `json` or `markdown`; `--max-chars` defaults to `12000` and must be at least `2000`.

The compiler calls the canonical selector and reads only paths in its manifest. A `complete` `context-pack/v1` preserves project, goal, selected paths, source-verification state, semantic items with source paths, structured review verdict and implementation gate, open items, effective rule provenance, and measurements. Whole optional items may be replaced by deduplicated `required_expansions` containing their field and selected source path. Open items, gate state, selection identity, and source-verification state are never silently truncated.

Exit `0` means a complete pack, exit `2` means incomplete or error, and exit `3` means no match. On a nonzero result, do not reinterpret it as success: use the unchanged selection manifest and existing document-reading order as the fallback. A required expansion permits reading only the named selected path for the named field; it never expands discovery scope.

## Manifest

Return bounded JSON containing `status`, `mode`, `project_id`, `record_root`, selected relative paths, source-verification requirement, and warnings. Never include record contents or secrets in the manifest.
