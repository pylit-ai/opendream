# tasks.md — 435-opendream-automations

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `435-opendream-automations` to `specs/registry.yaml`
- [x] T2: add automation schemas, storage paths, and validation hooks
- [x] T3: implement deterministic automation job registration, execution, state, and typed projection records
- [x] T4: add `opendream automation register|run|tick|status|review`
- [x] T5: integrate automation summaries into top-level `tick`, `status`, and `prepare-context`
- [x] T6: update architecture and README docs for the automation layer
- [x] T7: add automated verification for registration, execution, staleness, and status integration
- [x] T8: run `./.venv/bin/python -m unittest tests.test_memory_cli.MemoryCliIntegrationTests -v`
- [x] T9: run `./.venv/bin/python -m ruff check opendream tests scripts`
- [x] T10: run `./.venv/bin/python -m mypy opendream scripts`
- [x] T11: run `make verify`
- [x] T12: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: write the matching OpenSpec proposal bundle
- [x] [P] TP2: update docs once the automation status and context shapes stabilize

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] automation outputs remain separate from canonical durable memory
- [x] tests and verification commands pass
