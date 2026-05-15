# ADR-005: Isolated execution for code mutation

## Status
Proposed

## Context
Future automation may propose or apply code edits. Unattended jobs must not mutate the primary workspace directly.

## Decision
Engines with `code_mutation` side-effect class require isolated git worktrees, explicit approval policy, and structured run reports.

## Consequences
Primary workspace stays protected; operators review diffs from isolated runs before promotion.

## Alternatives considered
- Allow in-place mutation with warnings (rejected: irreversible drift)
- No code-mutation engines (rejected: blocks useful automations)

## References
- `docs/architecture/overview.md`
