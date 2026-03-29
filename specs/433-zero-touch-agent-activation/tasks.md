# tasks.md — 433-zero-touch-agent-activation

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `433-zero-touch-agent-activation` to `specs/registry.yaml`
- [x] T2: add activation and repair schemas to package, canonical spec, and proposal bundles
- [x] T3: implement activation, detection, registry persistence, and managed surfaces for supported targets
- [x] T4: add `doctor --surface agents`, repair, and `init --activate-configured`
- [x] T5: keep `service autowire` compatible while routing it through the activation layer
- [x] T6: add fixture-driven activation and release verification, including Codex wrapper exit-code coverage
- [x] T7: update README and adapter guidance for the activation-first operator path
- [x] T8: run `make verify`
- [x] T9: run `make release-check`
- [x] T10: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: write the matching OpenSpec proposal bundle
- [x] [P] TP2: update release blockers and docs once the CLI surface is stable

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] managed surfaces remain reversible and local-first
- [x] tests and release gates pass
