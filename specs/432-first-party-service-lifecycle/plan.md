# plan.md — 432-first-party-service-lifecycle

## Summary
Add a first-party lifecycle layer on top of the shipped dream worker. Keep the current local-first invariant: services only manage OpenDream-owned manifests, state, logs, and adapter glue inside explicit workspace paths.

## Architecture impact
- touched components:
  - `opendream.service`
  - `opendream.dream`
  - `opendream.storage`
  - `opendream.cli`
  - `opendream.validation`
  - release tooling, docs, and tests
- unchanged components:
  - durable record format
  - planner and verifier semantics
  - retrieval and observability read model contracts

## Data model / contract changes
- add service-install-report, worker-health, supervisor-manifest, and autowire-report schemas
- persist service manifest, service runtime, and worker health under `memory/state/`
- persist service and autowire reports under `memory/audit/service/` and `memory/audit/autowire/`
- package launchd and systemd templates for rendered manifest output

## Interfaces
- new CLI:
  - `opendream install-service`
  - `opendream uninstall-service`
  - `opendream update-service`
  - `opendream service start`
  - `opendream service stop`
  - `opendream service restart`
  - `opendream service status`
  - `opendream service doctor`
  - `opendream service autowire`
- existing CLI changed:
  - `opendream dream worker`
  - `opendream dream daemon`
  - `opendream dream status`

## Security / safety review
- auth changes: none
- secret handling: unchanged
- irreversible actions: none; uninstall preserves queue and memory state by default
- new trust boundary: adapter autowire edits only explicit OpenDream-managed paths and blocks unrelated file mutation

## Rollout
1. add service schemas, template assets, and storage locations
2. add service lifecycle and heartbeat code paths
3. wire new lifecycle commands into the CLI
4. update docs, specs, tests, and release smoke

## Rollback
1. remove the service lifecycle commands and ignore service state files
2. stop using autowire helpers and fall back to manual adapter snippets
3. keep dream queue and durable memory data unchanged

## Verification plan
- run: `./.venv/bin/python -m unittest tests.test_memory_cli -v`
- run: `./.venv/bin/python -m unittest tests.test_release_artifact -v`
- run: `./.venv/bin/python -m ruff check opendream tests scripts`
- run: `./.venv/bin/python -m mypy opendream scripts`
- run: `make verify`
- run: `make release-check`

## ADR needed?
- no
