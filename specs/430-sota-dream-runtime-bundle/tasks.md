# tasks.md — 430-sota-dream-runtime-bundle

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `430-sota-dream-runtime-bundle` to `specs/registry.yaml`
- [x] T2: add planner or verifier schemas and storage locations
- [x] T3: refactor consolidation into plan → verify → apply with audit artifacts
- [x] T4: implement `dream enqueue`, `dream worker`, and `dream daemon`
- [x] T5: add CLI integration coverage for planner artifacts and queued worker behavior
- [x] T6: update README, adapter examples, and release smoke for the worker path
- [x] T7: run `make verify`
- [x] T8: run `make release-check`
- [x] T9: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: schema-copy and proposal-bundle updates
- [x] [P] TP2: adapter README and script updates

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] planner or verifier fallbacks remain explicit
- [x] tests and release gates pass
