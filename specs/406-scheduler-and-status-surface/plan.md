# plan.md — 406-scheduler-and-status-surface

## Summary
Add a thin scheduler and status layer on top of `maintain` rather than a long-running process. Reuse maintenance state and lock files. Surface store health and runnable policy decisions in operator-facing JSON.

## Architecture impact
- touched components:
  - `opendream_memory.cli`
  - `opendream_memory.integration`
  - `opendream_memory.storage`
  - tests
  - `README.md`
  - adapter pack scripts and snippets
- unchanged components:
  - durable memory schemas
  - extractor and consolidator semantics

## Data model / contract changes
- no change to durable schemas
- scheduler policy lives in `memory/state/store.json`
- status responses include:
  - workspace
  - store kind
  - pending event count
  - pending candidate count
  - lock present or stale
  - last run time
  - next eligible run reason

## Interfaces
- new CLI commands:
  - `status`
  - `tick`
- optional flags:
  - `--stores-manifest`
  - `--min-new-events`
  - `--min-interval-seconds`
  - `--include-global`
  - `--global-workspace`

## Observability
- `status` returns machine-readable JSON
- `tick` returns skip or run reason just like `maintain`
- repeated invocations leave a clear audit trail through existing maintenance state

## Rollout
1. add spec and registry entry
2. implement `status` and `tick`
3. add tests
4. update docs and adapter examples
5. rerun `make verify`

## Rollback
1. remove `status` and `tick`
2. keep `maintain` and the core runtime intact

## Verification plan
- run: `make test`
- run: `make verify`
- manual checks:
  - call `status` before and after initialization
  - call `tick` repeatedly
  - create a lock and inspect status output

## ADR needed?
- no
