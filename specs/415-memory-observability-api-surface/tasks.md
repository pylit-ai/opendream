# tasks.md — 415-memory-observability-api-surface

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `415-memory-observability-api-surface` to `specs/registry.yaml`
- [ ] T2: define API contracts and pagination/filter query params
- [ ] T3: implement read endpoints for overview, memories, runs, retrievals, sessions, context, reviews, evals, and exports
- [ ] T4: implement lineage and diff endpoints
- [ ] T5: implement audited annotation and review-action write endpoints
- [ ] T6: add SSE or websocket updates for active runs and lock state
- [ ] T7: add endpoint tests for filtering, pagination, and broken-artifact tolerance
- [ ] T8: update docs with API usage and safety boundaries
- [ ] T9: run `make verify`
- [ ] T10: reconcile implementation against acceptance criteria

## Parallelizable
- [ ] [P] TP1: endpoint contract drafting
- [ ] [P] TP2: API fixture and pagination test coverage

## Completion checklist
- [ ] all acceptance criteria satisfied
- [ ] no constitution violations
- [ ] API remains a thin surface over the read model and source artifacts
