# tasks.md — 402-release-hardening

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add release-hardening spec bundle and registry entry
- [x] T2: package runtime schemas and add canonical schema copies under `specs/401.../schema/`
- [x] T3: add `pyproject.toml`, console entrypoint metadata, and release docs
- [x] T4: add automated schema-presence and install smoke tests
- [x] T5: update README and commands for release-safe usage
- [x] T6: run `make verify`
- [x] T7: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: release metadata docs
- [x] [P] TP2: schema-copy drift checks

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] rollback path documented
- [x] tests pass
