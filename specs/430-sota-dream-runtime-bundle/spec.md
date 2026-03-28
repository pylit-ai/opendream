# spec.md — 430-sota-dream-runtime-bundle

## Title
Add auditable planner or verifier contracts and a queue-backed background dream worker

## Why
OpenDream already ships transcript-native dreaming, review surfaces, fidelity evals, and release gates. The remaining blocker from the `blocker_removal.md` bundle is runtime discipline: consolidation decisions are still made inline inside the consolidator, and unattended dreaming depends on ad hoc `tick` usage instead of a durable queue-backed worker path.

This change adds explicit plan and verifier artifacts plus a first-party local dream worker. It reuses the existing retrieval, observability, review, eval, and release surfaces rather than replacing them.

## In scope
- deterministic dream-plan and verifier-report artifacts for every consolidation run
- optional local planner and verifier subprocess hooks with builtin fallbacks
- queue-backed `dream enqueue`, `dream worker`, and `dream daemon`
- durable queue and worker state under the memory root
- release and adapter guidance updated to expose the worker path
- canonical `430` spec bundle plus matching proposal-stage OpenSpec bundle committed to the repo

## Out of scope
- hosted daemons or remote services
- cloud-managed model routing
- replacing the existing retrieval, review UI, or fidelity-eval surfaces
- product-code mutation by background dreaming

## User-visible behavior
- consolidation writes a validated plan artifact and verifier report before durable memory mutation
- `dream status` exposes queue depth and worker state
- operators can enqueue dream work and drain it with `dream worker --once` or loop with `dream daemon`
- adapter example scripts kick the one-shot worker after normal maintenance
- release smoke covers the worker path in addition to `dream run` and `eval dream-fidelity`

## Acceptance criteria
- [x] AC-1: `consolidate` emits schema-valid dream-plan and verifier-report artifacts for every completed run
- [x] AC-2: builtin verifier blocks malformed or unsupported planner actions before durable writes
- [x] AC-3: `dream enqueue` persists queue state under the configured memory directory and `dream status` reports queue depth
- [x] AC-4: `dream worker --once` drains queued jobs safely and the queue survives process restarts
- [x] AC-5: `dream daemon` is an alias of the worker loop and honors custom memory directories
- [x] AC-6: adapter examples and release smoke exercise the worker path, not just manual `dream run`

## Edge cases
- worker lock held while a one-shot worker invocation is requested
- queued jobs with no explicit episode paths falling back to the transcript directory
- plan or verifier adapter failure falling back to builtin logic without silent mutation
- retrieval ranking pressure from the extra durable records created by planner-audited consolidation

## Required verifiers
- unit tests: yes, via deterministic CLI integration coverage of planner artifacts and queued worker behavior
- integration tests: yes, `tests.test_memory_cli`, `tests.test_release_artifact`, and `make release-check`
- evals / scenario checks: yes, `eval dream-fidelity` remains part of `make verify`
- manual verification: yes, run `dream enqueue`, `dream worker --once`, and inspect plan or verifier JSON under `memory/audit/`

## Risks
- a queue-backed worker is still local-process based, so operators remain responsible for how they keep it running
- optional adapter commands can produce unstable plans if operators point them at poor external tooling

## Links
- `../418-transcript-native-dream-engine/spec.md`
- `../417-memory-review-and-fidelity-tooling/spec.md`
- `../420-truthful-verification-and-release/spec.md`
- `../../notepads/active/blocker_removal.md`
