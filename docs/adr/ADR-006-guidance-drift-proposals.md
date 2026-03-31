# ADR-006: Guidance-drift proposals

## Status
Proposed

## Context
Repeated agent friction should improve repo guidance without silent policy rewrites.

## Decision
TBD — promote when WS7 lands. Analyzers emit reviewable proposal records; canonical docs change only via explicit human promotion or governed commands.

## Consequences
Automation produces evidence-backed suggestions; default path stays proposal-only.

## Alternatives considered
- Auto-edit AGENTS.md from logs (rejected: governance risk)
- No automated feedback loop (rejected: slow learning)

## References
- `openspec/changes/agent-ready-platform-complete/design/05-guidance-drift-automations.md`
