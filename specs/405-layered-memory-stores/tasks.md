# tasks.md — 405-layered-memory-stores

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `405-layered-memory-stores` to `specs/registry.yaml`
- [x] T2: add store metadata and config support for `project` and `global`
- [x] T3: implement store-group manifest loading and validation
- [x] T4: extend `prepare-context` for multi-store composition
- [x] T5: extend `maintain` for deterministic multi-store execution
- [x] T6: add routing flags for event emission
- [x] T7: add integration tests for precedence and conflict behavior
- [x] T8: add README section for `~/.opendream-global` plus repo-local usage
- [x] T9: create ADR-002 for layered-store precedence
- [x] T10: run `make verify`
- [x] T11: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: README and docs updates
- [x] [P] TP2: fixture creation for multi-store tests
- [x] [P] TP3: ADR drafting

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] precedence rules documented
- [x] multi-store tests pass
