# plan.md — 435-opendream-automations

## Summary
Layer a managed automation subsystem on top of the current OpenDream runtime. The implementation should reuse the existing scheduler-safe `tick`, status aggregation, and filesystem-backed audit model while keeping automation outputs separate from canonical durable memory.

## Architecture impact
- touched components:
  - `opendream.storage`
  - `opendream.models`
  - `opendream.validation`
  - `opendream.integration`
  - `opendream.cli`
  - docs and tests
- new components:
  - `opendream.automation`
- unchanged components:
  - durable memory record semantics
  - dream queue semantics and service supervisor rendering
  - activation and managed-surface repair logic

## Data model / contract changes
- add automation job and automation run schemas
- persist automation jobs, per-job state, and per-type records under a dedicated `automation/` subtree inside the memory root
- keep automation records separate from `state/durable_records.json`
- expose automation summaries in top-level status and prompt context as a separate layer

## Interfaces
- new CLI:
  - `opendream automation register`
  - `opendream automation run`
  - `opendream automation tick`
  - `opendream automation status`
  - `opendream automation review`
- existing CLI changed:
  - `opendream tick`
  - `opendream status`
  - `opendream prepare-context`

## Security / safety review
- auth changes: none
- secret handling: unchanged; automation inputs remain local filesystem memory artifacts
- irreversible actions: none; automation commands only write within the memory root
- new trust boundary: automation records become operator-visible projections and therefore must remain obviously distinct from canonical durable memory

## Rollout
1. add canonical and proposal spec bundles plus registry entry
2. add automation schemas, models, and storage layout
3. implement deterministic automation execution and record consolidation
4. wire CLI plus top-level tick or status or context integration
5. update docs and add automated verification

## Rollback
1. remove the automation subcommands and storage paths
2. stop surfacing automation summaries from top-level status and context assembly
3. keep existing memory, dream, and activation flows unchanged

## Verification plan
- run: `./.venv/bin/python -m unittest tests.test_memory_cli.MemoryCliIntegrationTests -v`
- run: `./.venv/bin/python -m ruff check opendream tests scripts`
- run: `./.venv/bin/python -m mypy opendream scripts`
- run: `make verify`

## ADR needed?
- no
