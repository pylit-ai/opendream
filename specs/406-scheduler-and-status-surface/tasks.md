# tasks.md — 406-scheduler-and-status-surface

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `406-scheduler-and-status-surface` to `specs/registry.yaml`
- [x] T2: implement `status` command
- [x] T3: implement `tick` command as a thin policy wrapper around `maintain`
- [x] T4: add stale-lock and repeated-invocation tests
- [x] T5: update adapter docs to prefer `tick` and `status`
- [x] T6: update `README.md` with cron examples
- [x] T7: run `make verify`
- [x] T8: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: docs and cron examples
- [x] [P] TP2: lock-state tests

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] tests pass
