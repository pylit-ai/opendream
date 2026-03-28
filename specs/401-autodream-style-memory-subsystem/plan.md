# plan.md — 401-autodream-style-memory-subsystem

## Summary
Implement the subsystem as a standard-library Python package with a small CLI and file-backed store. Keep the runtime deterministic, auditable, and local-first, then back it with fixture-driven tests and a working Makefile.

## Architecture impact
- touched components:
  - new Python runtime under `src/opendream/`
  - new automated tests and fixtures under `tests/`
  - repository commands in `Makefile`
  - canonical spec bundle for this change
- unchanged components:
  - MCP docs and adapter surfaces outside routing updates already staged

## Data model / contract changes
- add event, candidate, durable record, startup index, and consolidation-op runtime models
- persist durable records in `memory/state/durable_records.json`
- generate markdown views in `memory/MEMORY.md` and `memory/topics/*.md`
- emit audit artifacts in `memory/audit/`

## Interfaces
- input: CLI commands for `init`, `append-event`, `extract`, `bootstrap-index`, `consolidate`, `retrieve`, and `demo`
- output: JSON on stdout plus filesystem artifacts under `memory/`

## Observability
- logs: CLI JSON summaries and audit run metadata
- metrics: deterministic counts in run summaries and retrieval traces
- traces: consolidation operation logs, retrieval audit logs, bootstrap report

## Security / safety review
- auth changes: none
- secret handling: events marked `secret`, `sensitive`, or `do_not_store` are never promoted
- external services: none
- irreversible actions: none; the store is local and auditable

## Rollout
1. create canonical spec and registry entries
2. implement runtime package and CLI
3. add fixtures, tests, and working Make targets
4. verify end-to-end with deterministic runs

## Rollback
1. remove the runtime package, tests, and Makefile targets
2. mark the spec inactive or superseded in `specs/registry.yaml`

## Verification plan
- run: `make lint`
- run: `make typecheck`
- run: `make test`
- run: `make verify`
- manual checks:
  - run the demo command and inspect generated `memory/`
  - confirm consolidation does not modify files outside the memory store

## ADR needed?
- no
