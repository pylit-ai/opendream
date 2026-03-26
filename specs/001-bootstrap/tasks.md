# tasks.md — 001-bootstrap

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [ ] T1: read `NORTHSTAR.md`, `CONSTITUTION.md`, `PRD.md`, `spec.md`, and `plan.md`
- [ ] T2: create or update contracts / schemas
- [ ] T3: implement core domain logic
- [ ] T4: implement boundary adapters and API handlers
- [ ] T5: add structured logging and metrics
- [ ] T6: write unit tests
- [ ] T7: write integration tests
- [ ] T8: update docs impacted by behavior changes
- [ ] T9: run `make verify`
- [ ] T10: reconcile implementation against acceptance criteria

## Parallelizable
- [ ] [P] TP1: docs updates that do not affect code behavior
- [ ] [P] TP2: non-overlapping test additions

## Completion checklist
- [ ] all acceptance criteria satisfied
- [ ] no constitution violations
- [ ] rollback path documented
- [ ] observability added
- [ ] tests pass
