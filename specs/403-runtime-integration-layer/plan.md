# plan.md — 403-runtime-integration-layer

## Summary
Implement a thin integration layer in the existing CLI and runtime package. Keep it deterministic, stateless where possible, and compatible with repeated cron invocation.

## Architecture impact
- touched components:
  - `opendream.cli`
  - new integration helpers for maintenance and prompt rendering
  - tests and README examples
- unchanged components:
  - core schema bundle and packaging surface

## Data model / contract changes
- add maintenance state under `memory/state/maintenance_state.json`
- no change to durable memory schemas

## Interfaces
- input: `emit-event`, `maintain`, and `prepare-context` CLI commands
- output: JSON summaries and prompt-ready markdown context

## Observability
- maintenance returns explicit `status` and `reason` fields for skip vs run
- prompt preparation returns selected ids and rendered context together

## Security / safety review
- auth changes: none
- secret handling: event emission still validates sensitivity and storage rules through the existing engine
- external services: none
- irreversible actions: none

## Rollout
1. add spec and registry entry
2. implement integration helpers and CLI commands
3. add tests and README usage
4. rerun `make verify`

## Rollback
1. remove the integration commands and helper module
2. keep the memory engine and package contract unchanged

## Verification plan
- run: `make test`
- run: `make verify`
- manual checks:
  - emit a project decision without a JSONL file
  - call `maintain` twice and observe run then skip
  - call `prepare-context` and inspect the prompt block

## ADR needed?
- no
