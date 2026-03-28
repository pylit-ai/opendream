# plan.md — 417-memory-review-and-fidelity-tooling

## Summary
Layer review workflows and advanced fidelity tooling on top of the MVP UI. Keep graphs secondary, maintain explicit audit trails, and make AutoDream-style behavior measurable rather than rhetorical.

## Architecture impact
- touched components:
  - review queue and action handlers
  - provenance graph query and rendering layer
  - fidelity diagnostics and metrics aggregation
  - export builder and redaction policy
  - tests and seeded datasets
- unchanged components:
  - source-of-truth artifact layout
  - basic read-only observability flows

## Fidelity surfaces
- Dream Phase Map
- Lean Index Budget View
- Read-only code / write-memory guardrail indicator
- Activation diagnostics
- Transcript-vs-event coverage

## Review rules
- triage first, editing second
- queue reason visible before opening detail
- bulk actions limited to homogeneous item types
- every action writes an audit record with actor and rationale

## Graph rules
- cap node count by default
- expand only from selected nodes
- preserve deep links into underlying detail drawers

## Rollout
1. add spec and registry entry
2. implement review queue and audited actions
3. implement fidelity diagnostic aggregates and panels
4. implement focused provenance graph
5. implement eval and export surfaces
6. rerun verification

## Rollback
1. remove review and advanced tooling surfaces
2. keep MVP observability intact

## Verification plan
- run: full test suite including review and export coverage
- manual checks:
  - triage a contested memory
  - inspect transcript-vs-event coverage on a seeded run
  - export a run bundle and reconstruct the diff offline

## ADR needed?
- no
