# plan.md — 413-authoritative-release-gate

## Summary
Replace the current release wrapper with an explicit Python orchestrator that runs deterministic, time-bounded stages inside temp workdirs and emits a release manifest plus summary markdown on every attempt.

## Architecture impact
- touched components:
  - release-check script and Make target
  - atomic write helpers in runtime storage
  - packaging smoke and concurrency stress tests
  - README verification section
- unchanged components:
  - package name and console entrypoint
  - local-first runtime model

## Data model / contract changes
- add `release_manifest.json`
- add `release_summary.md`

## Interfaces
- input: `make release-check`, `python3 scripts/release_check.py`
- output: per-stage verdicts plus release manifest and summary

## Observability
- per-stage durations
- command list and artifact hashes
- deterministic overall verdict

## Security / safety review
- auth changes: none
- secret handling: no secrets should enter the manifest
- irreversible actions: none

## Rollout
1. add canonical spec bundle
2. implement orchestrator and atomic writes
3. add packaging and concurrency coverage
4. update docs and Make targets

## Rollback
1. restore previous `release-check` target
2. remove manifest generation and stress tests

## Verification plan
- run: `make release-check`
- run: seeded failure stage in tests
- inspect emitted manifest and summary

## ADR needed?
- no
