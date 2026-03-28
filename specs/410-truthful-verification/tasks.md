# tasks.md — 410-truthful-verification

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `410-truthful-verification` to `specs/registry.yaml`
- [x] T2: replace placeholder lint and typecheck with real tool-backed commands and checked-in config
- [x] T3: add deterministic verification orchestration and `verification_report.json`
- [x] T4: add schema/property-style tests and adversarial regression probes
- [x] T5: add write summary plus diff artifacts for direct mutations and consolidation
- [x] T6: align README and release language to the real gate
- [x] T7: run `make verify`
- [x] T8: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: README and docs updates
- [x] [P] TP2: adversarial probe fixtures

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] verification report emitted
- [x] tests pass
