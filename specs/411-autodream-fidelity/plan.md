# plan.md — 411-autodream-fidelity

## Summary
Add a bounded DreamRunner on top of the existing event and consolidation runtime. Dream runs read transcript and log episodes, normalize dates, stage memory-worthy events, reuse the existing consolidator, and persist dream status plus compatibility views.

## Architecture impact
- touched components:
  - new episode ingestion and dream orchestration modules
  - CLI subcommands and status payloads
  - storage path resolution and compatibility file generation
  - tests and fixtures for transcript-driven dreaming
- unchanged components:
  - external service boundaries
  - local-first storage model

## Data model / contract changes
- add dream status state
- add optional workspace config for memory directory and compatibility mode
- add transcript/log episode fixture schema

## Interfaces
- input: `opendream dream run`, `status`, `tick`, transcript/log JSONL fixtures
- output: durable memory, dream audits, status metadata, and compatibility markdown views

## Observability
- explicit phase list per dream run
- last dream run timestamps and selected-signal counts

## Security / safety review
- auth changes: none
- secret handling: dream ingestion must keep honoring sensitivity filters
- irreversible actions: none

## Rollout
1. add canonical spec bundle
2. add workspace config and path-safe storage helpers
3. implement episodes and DreamRunner
4. update CLI, tests, and docs

## Rollback
1. remove dream-specific commands and config
2. restore status payload to pre-dream shape

## Verification plan
- run: `python3 -m unittest tests.test_memory_cli -v`
- run: `make verify`
- manual checks:
  - run `opendream dream run --episodes ...`
  - inspect `status` and compat files

## ADR needed?
- no
