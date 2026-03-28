# spec.md — 413-authoritative-release-gate

## Title
Make release-check authoritative, hermetic, and non-hanging

## Why
The current release gate is a thin wrapper around `verify` plus one test module. That is not a trustworthy release decision. This change makes `make release-check` a deterministic orchestrator with time bounds, isolated workdirs, packaging smoke, concurrency stress coverage, and a release manifest.

## In scope
- explicit release-check orchestrator
- per-stage timeouts and deterministic failure reporting
- isolated temp-dir execution
- sdist and wheel build plus clean-venv install smoke
- release manifest and summary markdown
- release blocking when 410-412 are incomplete
- atomic write helpers and concurrency stress coverage

## Out of scope
- hosted release pipelines
- artifact signing infrastructure
- external publishing workflows

## User-visible behavior
- `make release-check` either passes honestly or fails with a clear stage verdict.
- Every release-check emits a manifest with environment, commands, verdict, and hashes.
- No stage hangs forever.

## Acceptance criteria
- [ ] AC-1: `make release-check` completes successfully on a clean machine or container
- [ ] AC-2: seeded regressions fail deterministically with a stage-level verdict
- [ ] AC-3: no release-check stage can hang indefinitely
- [ ] AC-4: packaging smoke builds wheel and sdist, installs into a clean venv, and runs CLI smoke commands
- [ ] AC-5: a release manifest is emitted on every run
- [ ] AC-6: release readiness remains blocked unless 410-412 all pass

## Edge cases
- missing build dependencies
- parallel release-check invocations
- partial artifacts from interrupted runs
- deadlocks during concurrent memory mutation tests

## Required verifiers
- unit tests: yes, manifest and timeout helpers
- integration tests: yes, isolated release-check smoke runs
- evals / scenario checks: no
- manual verification: yes, run `make release-check`

## Risks
- isolated release smoke can be slow if environments are recreated wastefully
- overly broad locking can create false negatives in concurrent runs

## Links
- `../../README.md`
- `../../specs/410-truthful-verification/spec.md`
