# Change: Make release-check authoritative, hermetic, and non-hanging

## Why
A release gate that hangs or only passes in fragments is not a release gate. It needs time bounds, isolated workdirs, packaging smoke, concurrency checks, and an emitted manifest.

## What Changes
- replace the thin release wrapper with an explicit orchestrator
- add timeouts, isolated temp dirs, packaging smoke, and manifests
- add atomic writes and concurrency stress coverage
- block release readiness unless 410-412 are complete

## Impact
- Affected specs: `413-authoritative-release-gate`
- Affected code: `scripts/`, `Makefile`, `tests/`, `opendream_memory/`, `README.md`
