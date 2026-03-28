# tasks.md — 411-autodream-fidelity

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `411-autodream-fidelity` to `specs/registry.yaml`
- [x] T2: add workspace config support for custom memory directories and compatibility mode
- [x] T3: implement episode ingestion for transcripts, logs, and existing events
- [x] T4: implement DreamRunner with explicit phases and bounded signal gathering
- [x] T5: add date normalization and dream status persistence
- [x] T6: expose `opendream-memory dream run` and wire status or tick integration
- [x] T7: add transcript-only, custom-path, and dream-lock tests
- [x] T8: update README and architecture docs
- [x] T9: run `make verify`
- [x] T10: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: transcript fixture authoring
- [x] [P] TP2: README and architecture updates

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] dream status visible
- [x] tests pass
