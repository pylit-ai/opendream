# tasks.md — 404-framework-adapter-pack

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `404-framework-adapter-pack` to `specs/registry.yaml`
- [x] T2: create `.meta/spec-adapters/claude-code/` with README, example settings, skill, and wrapper scripts
- [x] T3: create `.meta/spec-adapters/codex/` with README, AGENTS examples, skill, and wrapper scripts
- [x] T4: create `.meta/spec-adapters/openclaw/` with README, event map, prompt snippets, and hook script
- [x] T5: add adapter smoke validator under `scripts/check_adapters.py`
- [x] T6: update `README.md` with adapter-pack section
- [x] T7: run `python3 scripts/check_adapters.py`
- [x] T8: run `make verify`
- [x] T9: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: Claude Code adapter docs
- [x] [P] TP2: Codex adapter docs
- [x] [P] TP3: OpenClaw adapter docs

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] adapter files remain non-normative
- [x] tests and smoke checks pass
