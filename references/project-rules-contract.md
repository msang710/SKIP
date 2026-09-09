# SKIP Core customization and Project Rules contract

## Authority

Only an explicitly approved `--setup` diff may change persistent Core customization or Project Rules. Repeated preferences, repository conventions, project-profile contents, and agent memory are not authority.

## Storage

```text
<record-root>/config/core-rules.yaml
<record-root>/projects/<project-id>/project-rules.yaml
```

Files are external records and use JSON-compatible YAML for deterministic stdlib parsing. Absence is normal.

Core configuration requires `version`, `disabled_default_rule_ids`, and `custom_rules`. Custom rules require `id`, `invariant`, `detail`, `status`, and `authority.changed_at`.

Project Rules requires `version`, `project_id`, and `rules`. Rules require `id`, `rule`, `scope`, `status`, and `authority.changed_at`. `scope.kind` is `project` or `environment-operation`; the latter also requires stable `environment_id` and `operation`.

Do not store conversation transcripts. `rationale`, `exceptions`, `verification`, and `last_verified` are optional. Normative rules do not replace FACT.

## Setup flow

Run `skip` without arguments to use the keyboard-first setup UI. The public interactive flow has two choices: bundled Core rule toggles and verbatim project-specific rules. Arrow keys move, Space toggles, Enter selects or applies, and Escape cancels. The lower-level `intent_context.py setup` flags remain an automation and test surface; users do not need to memorize them.

1. Resolve the exclusive record root and project.
2. Show effective rules and provenance without writing.
3. Build and validate an exact proposed diff.
4. Show scope and affected IDs.
5. Apply only after explicit approval.
6. Use atomic replacement and retain a recoverable previous copy when overwriting.

Environment-specific commands are projected only when project, environment, operation, and workflow stage all match.
