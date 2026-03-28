# tasks.md — 414-memory-observability-read-model

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `414-memory-observability-read-model` to `specs/registry.yaml`
- [x] T2: define typed schemas for `ContextAssembly`, `ConsolidationOp`, `Annotation`, `ReviewDecision`, and `PhaseTrace`
- [x] T3: implement the observability indexer/backfill command
- [x] T4: add provenance-preserving aggregate queries for overview surfaces
- [x] T5: add fixtures for seeded runs, retrievals, and partial artifacts
- [x] T6: add tests for idempotent backfill and broken-artifact tolerance
- [x] T7: update `README.md` or docs for the read-model/indexer workflow
- [x] T8: run `make verify`
- [x] T9: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: fixture creation for runs, retrievals, and context assembly
- [x] [P] TP2: schema drafting for new observability entities

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] read model remains non-authoritative relative to source files
