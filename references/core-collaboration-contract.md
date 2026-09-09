# SKIP core collaboration contract

## Default rules

| ID | Compact invariant |
|---|---|
| C-001 | Use explicit model language, otherwise current conversation language; preserve technical names. |
| C-002 | Treat a user's FACT correction as a counterclaim and reinvestigate current evidence. |
| C-003 | Return FACT corrected, existing FACT retained, or EVIDENCE_PENDING. |
| C-004 | Split work at valid, testable system states. |
| C-005 | Mark indivisible spans atomic and include containment and recovery. |
| C-006 | Do not substitute one evidence surface for another. |
| C-007 | Judge completion by the requested observable outcome. |
| C-008 | Preserve NOT_RUN, partial verification, gaps, and EVIDENCE_PENDING. |
| C-009 | Approval covers only the named artifact and scope. |
| C-010 | Do not implicitly clean, restore, migrate, or delete unrelated work or records. |

## FACT counterclaims

A material correction triggers the same investigation needed to write a new plan for that claim: relevant callers, reads, writes, schemas, configuration, tests, and available runtime evidence. Search for evidence that can falsify either claim. Update downstream artifacts only when the resolved FACT changes them.

## Evidence surfaces

Source, test, build, package, install, runtime, GUI interaction, device, and production are separate evidence states. A lower surface may be a prerequisite but never proves a higher one.

## Stable boundaries

Prefer additive structure, compatible caller migration, explicit activation, observation, and separately approved retirement. Do not force dual-write where it creates divergence. If no safe intermediate state exists, declare the atomic span, containment, rollback, and recovery evidence.

## Interaction steering

Core requires scope, assumptions and uncertainty, approval boundary, verification state, next decision or gate, and completion state. Provider adapters choose channels, timing, buttons, plan surfaces, and layout.

Keep the complete state in structured/detail output and show result, checks, and remaining decisions by default. Relevant failure, stale authority, missing verification and scope ambiguity must remain visible. Reuse existing valid approval for the same target/digest and scope; report changed targets instead of restarting the approval conversation. See [workflow-runtime-contract.md](workflow-runtime-contract.md).
