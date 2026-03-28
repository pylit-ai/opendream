# tasks.md — 419-dream-fidelity-evals

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `419-dream-fidelity-evals` to `specs/registry.yaml`
- [x] T2: add the packaged transcript fixture and `eval dream-fidelity` runtime
- [x] T3: add repo-local CLI coverage and clean-venv smoke coverage for the new eval
- [x] T4: update README examples and verification language for dream fidelity
- [x] T5: run `./.venv/bin/python -m unittest tests.test_memory_cli tests.test_release_artifact -v`
- [x] T6: run `make verify`
- [x] T7: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: packaged fixture authoring
- [x] [P] TP2: README and verification-surface updates

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] dream fidelity is measured directly rather than inferred
- [x] tests pass
