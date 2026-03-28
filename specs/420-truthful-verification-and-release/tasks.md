# tasks.md — 420-truthful-verification-and-release

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `420-truthful-verification-and-release` to `specs/registry.yaml`
- [x] T2: add dream-fidelity coverage to `scripts/verify.py`
- [x] T3: extend `scripts/release_check.py` with installed-package `dream run` and `eval dream-fidelity`
- [x] T4: switch release blocker preference to the `418-420` task bundles when present
- [x] T5: update README verification and release language to match the actual gate
- [x] T6: run `make verify`
- [x] T7: run `make release-check`
- [x] T8: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: README and spec updates
- [x] [P] TP2: clean-venv smoke coverage

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] verification and release manifests include transcript-native dream stages
- [x] full gates pass
