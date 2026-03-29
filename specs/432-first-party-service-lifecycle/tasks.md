# tasks.md — 432-first-party-service-lifecycle

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `432-first-party-service-lifecycle` to `specs/registry.yaml`
- [x] T2: add service lifecycle templates, schemas, and storage locations
- [x] T3: implement `install-service`, `uninstall-service`, `update-service`, and `service start|stop|restart`
- [x] T4: implement worker heartbeat persistence plus `service status` and `service doctor`
- [x] T5: implement reversible adapter autowire support and reporting
- [x] T6: add CLI integration and release-smoke coverage for lifecycle and autowire flows
- [x] T7: update README and adapter docs for the lifecycle path
- [x] T8: run `make verify`
- [x] T9: run `make release-check`
- [x] T10: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: copy schema assets into canonical and proposal bundles
- [x] [P] TP2: write docs and adapter guidance updates

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] service lifecycle remains explicit and local-first
- [x] tests and release gates pass
