# tasks.md — 418-transcript-native-dream-engine

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `418-transcript-native-dream-engine` to `specs/registry.yaml`
- [x] T2: add transcript-directory resolution plus `dream status` and `dream tick`
- [x] T3: extend dream summaries and dream state with bounded-search reporting and last-run metadata
- [x] T4: add transcript-backlog, nested dream-command, and compat-path test coverage
- [x] T5: update README runtime guidance for transcript-native dreaming
- [x] T6: run `./.venv/bin/python -m unittest tests.test_memory_cli -v`
- [x] T7: run `make verify`
- [x] T8: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: README and spec updates
- [x] [P] TP2: transcript-fixture and dream CLI test coverage

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] dream status is inspectable without opening raw state files
- [x] tests pass
