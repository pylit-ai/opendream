# tasks.md — 434-zero-touch-activation-and-command-surface-compression

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `434-zero-touch-activation-and-command-surface-compression` to `specs/registry.yaml`
- [x] T2: add compressed status and target-registry schemas to package, canonical spec, and proposal bundles
- [x] T3: implement compressed activation-state or target-registry persistence and aggregated top-level status
- [x] T4: implement `opendream deactivate` and keep managed-surface removal reversible
- [x] T5: add migration hints and demote advanced `service` or `dream` surfaces in primary help text
- [x] T6: update README and adapter docs to the compressed normal path
- [x] T7: add fixture and release verification for status and deactivate
- [x] T8: run `make verify`
- [x] T9: run `make release-check`
- [x] T10: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: write the matching OpenSpec proposal bundle
- [x] [P] TP2: update release blockers and docs once the compressed help surface is stable

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] advanced commands remain available but secondary
- [x] tests and release gates pass
