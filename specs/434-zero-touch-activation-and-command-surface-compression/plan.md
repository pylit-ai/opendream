# plan.md — 434-zero-touch-activation-and-command-surface-compression

## Summary
Layer a compressed UX on top of the existing activation and service machinery. The implementation should keep `433` intact, but move the top-level contract to init/activate/status/repair/deactivate and make `status` the main operator answer instead of requiring separate doctor or service archaeology in the common path.

## Architecture impact
- touched components:
  - `opendream.activation`
  - `opendream.cli`
  - `opendream.validation`
  - docs, schemas, and tests
- unchanged components:
  - dream queue semantics
  - service supervisor rendering and worker health persistence
  - durable memory file formats and observability APIs

## Data model / contract changes
- add `activation-state`, `target-registry`, and `compressed-status` schemas
- persist compressed activation state under repo-local `.opendream/`
- keep `.opendream/agents.json` compatible while introducing `.opendream/targets.json` and activation-state artifacts for the compressed contract
- add an inspectable deactivation report under `.opendream/reports/`

## Interfaces
- new CLI:
  - `opendream deactivate`
- existing CLI changed:
  - `opendream status`
  - `opendream activate`
  - `opendream init --activate-configured`
  - advanced `service` and `dream` help text

## Security / safety review
- auth changes: none
- secret handling: unchanged
- irreversible actions: none; `deactivate` removes only managed surfaces and preserves unrelated content
- new trust boundary: compressed status becomes the primary operator summary and therefore must remain faithful to underlying registry and runtime state

## Rollout
1. add canonical and proposal schema assets plus the `434` spec bundle
2. extend activation with compressed status and deactivate
3. wire CLI help and migration hints
4. update README and adapter docs to the compressed standard path
5. add fixture and release verification for status and deactivate

## Rollback
1. remove `deactivate`
2. restore the prior top-level status shape
3. keep activation and advanced service or dream commands available as before

## Verification plan
- run: `./.venv/bin/python -m unittest tests.test_memory_cli -v`
- run: `./.venv/bin/python -m unittest tests.test_release_artifact -v`
- run: `./.venv/bin/python -m ruff check opendream tests scripts`
- run: `./.venv/bin/python -m mypy opendream scripts`
- run: `make verify`
- run: `make release-check`

## ADR needed?
- no
