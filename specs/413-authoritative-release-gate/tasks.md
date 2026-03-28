# tasks.md — 413-authoritative-release-gate

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `413-authoritative-release-gate` to `specs/registry.yaml`
- [x] T2: implement a time-bounded release-check orchestrator
- [x] T3: add isolated temp-dir execution and packaging smoke
- [x] T4: add release manifest and summary markdown generation
- [x] T5: add atomic write helpers and concurrency stress coverage
- [x] T6: block release readiness unless 410-412 are complete
- [x] T7: update README verification and release sections
- [x] T8: run `make release-check`
- [x] T9: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: release docs updates
- [x] [P] TP2: concurrency fixture authoring

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] release manifest emitted
- [x] release-check passes
