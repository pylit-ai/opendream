# tasks.md — 442-observe-health-and-live-check

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `442-observe-health-and-live-check` to `specs/registry.yaml`
- [x] T2: add failing tests for the health API and live-check path
- [x] T3: implement `GET /api/health` and `POST /api/health/live-check`
- [x] T4: ensure probe events do not create durable memory
- [x] T5: expose health evidence and live-check controls in the overview UI
- [x] T6: update observe-serve docs
- [x] T7: run `make verify`
- [x] T8: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: API contract tests
- [x] [P] TP2: overview UI marker updates

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] health remains evidence-first and local-first
