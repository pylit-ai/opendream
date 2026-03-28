# tasks.md — 414-memory-observability-read-model

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `414-memory-observability-read-model` to `specs/registry.yaml`
- [ ] T2: define typed schemas for `ContextAssembly`, `ConsolidationOp`, `Annotation`, `ReviewDecision`, and `PhaseTrace`
- [ ] T3: implement the observability indexer/backfill command
- [ ] T4: add provenance-preserving aggregate queries for overview surfaces
- [ ] T5: add fixtures for seeded runs, retrievals, and partial artifacts
- [ ] T6: add tests for idempotent backfill and broken-artifact tolerance
- [ ] T7: update `README.md` or docs for the read-model/indexer workflow
- [ ] T8: run `make verify`
- [ ] T9: reconcile implementation against acceptance criteria

## Parallelizable
- [ ] [P] TP1: fixture creation for runs, retrievals, and context assembly
- [ ] [P] TP2: schema drafting for new observability entities

## Completion checklist
- [ ] all acceptance criteria satisfied
- [ ] no constitution violations
- [ ] read model remains non-authoritative relative to source files
