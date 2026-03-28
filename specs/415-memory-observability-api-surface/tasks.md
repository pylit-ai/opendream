# tasks.md — 415-memory-observability-api-surface

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `415-memory-observability-api-surface` to `specs/registry.yaml`
- [x] T2: define API contracts and pagination/filter query params
- [x] T3: implement read endpoints for overview, memories, runs, retrievals, sessions, context, reviews, evals, and exports
- [x] T4: implement lineage and diff endpoints
- [x] T5: implement audited annotation and review-action write endpoints
- [x] T6: add SSE or websocket updates for active runs and lock state
- [x] T7: add endpoint tests for filtering, pagination, and broken-artifact tolerance
- [x] T8: update docs with API usage and safety boundaries
- [x] T9: run `make verify`
- [x] T10: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: endpoint contract drafting
- [x] [P] TP2: API fixture and pagination test coverage

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] API remains a thin surface over the read model and source artifacts
