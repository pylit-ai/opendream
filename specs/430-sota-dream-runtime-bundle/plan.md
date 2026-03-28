# plan.md — 430-sota-dream-runtime-bundle

## Summary
Layer planner and verifier contracts plus a first-party worker queue on top of the shipped transcript-native runtime. Keep the existing local-first invariants: models never write memory directly, worker state stays inside the memory root, and review or observability surfaces continue to read auditable artifacts instead of hidden state.

## Architecture impact
- touched components:
  - `opendream.consolidator`
  - `opendream.planner`
  - `opendream.verifier`
  - `opendream.dream`
  - `opendream.storage`
  - `opendream.cli`
  - adapter example scripts
  - release tooling and docs
- unchanged components:
  - durable record schema and retrieval file format
  - existing observability read model and API contracts
  - dream-fidelity eval semantics

## Data model / contract changes
- add `dream-plan.schema.json`, `verifier-report.schema.json`, and `dream-job.schema.json`
- persist plan and verifier audits under `memory/audit/plans/` and `memory/audit/verifier/`
- persist queue and worker state under `memory/state/dream_queue.json` and `memory/state/dream_worker_state.json`
- enrich `dream status` with queue depth, queued jobs, and worker state

## Interfaces
- new CLI:
  - `opendream dream enqueue`
  - `opendream dream worker`
  - `opendream dream daemon`
- existing CLI changed:
  - `opendream consolidate`
  - `opendream dream status`

## Observability
- consolidation summaries now link to planner and verifier artifacts
- worker runs emit their own diff or summary audit
- adapters surface the worker path in example post-task hooks

## Security / safety review
- auth changes: none
- secret handling: unchanged; queue and plan payloads stay inside the existing memory root
- irreversible actions: none
- new trust boundary: optional planner or verifier subprocess hooks are operator-owned and explicitly non-default

## Rollout
1. add schemas and storage locations for plan, verifier, queue, and worker state
2. refactor consolidation to plan → verify → apply
3. add queue-backed worker commands and status fields
4. update docs, adapters, and release smoke

## Rollback
1. revert to inline consolidator logic
2. stop invoking `dream worker` from adapter examples
3. ignore the new audit directories and queue files; durable memory data remains compatible

## Verification plan
- run: `./.venv/bin/python -m unittest tests.test_memory_cli -v`
- run: `./.venv/bin/python -m unittest tests.test_release_artifact -v`
- run: `./.venv/bin/python -m ruff check opendream tests scripts`
- run: `./.venv/bin/python -m mypy opendream scripts`
- run: `make verify`
- run: `make release-check`

## ADR needed?
- no
