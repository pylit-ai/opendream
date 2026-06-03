# ADR-006: Guidance-drift proposals

## Status
Proposed

## Context
Repeated agent friction should improve repo guidance without silent policy rewrites.

## Decision
Analyzers emit reviewable proposal records; canonical docs change only via explicit human promotion or governed commands.

## Consequences
Automation produces evidence-backed suggestions; default path stays proposal-only.

## Alternatives considered
- Auto-edit AGENTS.md from logs (rejected: governance risk)
- No automated feedback loop (rejected: slow learning)

## References
- `docs/architecture/overview.md`
