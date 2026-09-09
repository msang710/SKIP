# Optional external project profile contract

Use `<record-root>/projects/<project-id>/project-profile.md` only when project-specific routing or verification conventions recur and are not already clear in `AGENTS.md` or maintained repository documentation. Do not create or modify it without user authorization.

## Precedence

Apply guidance in this order:

1. current explicit user request
2. system and closest applicable repository instructions
3. external project profile
4. maintained repository documentation
5. conventions verified in executable code and tests

Executable code and observed results remain evidence of current behavior. Record conflicts instead of silently choosing a convenient source.

## Recommended sections

```markdown
# SKIP project profile

## Project purpose and terminology
## Specification language and conventions
## Architecture and source map
## Data, API, permission, and integration entry points
## Test, type, lint, build, migration, and verification commands
## Deployment, rollout, rollback, and operational constraints
## Known documentation and code conflicts
```

Keep the profile concise and portable. Use repository-relative paths. Store only durable routing facts; never store secrets, machine paths, temporary branch state, speculative architecture, feature decisions, or duplicated maintained documentation.

Verify profile claims when they affect the task. Propose rather than silently apply profile corrections.
