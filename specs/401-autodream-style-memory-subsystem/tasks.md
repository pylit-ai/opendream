# tasks.md — 401-autodream-style-memory-subsystem

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: create canonical spec bundle and registry entry for the memory subsystem
- [x] T2: implement runtime models, validation, storage, and CLI commands
- [x] T3: implement extraction, bootstrap indexing, consolidation, and retrieval logic
- [x] T4: add deterministic fixtures, integration tests, and concurrency coverage
- [x] T5: wire repository commands in `Makefile`
- [x] T6: run `make verify`
- [x] T7: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: fixture authoring and acceptance-style test cases
- [ ] [P] TP2: markdown documentation for the runtime layout

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] rollback path documented
- [x] observability added
- [x] tests pass
