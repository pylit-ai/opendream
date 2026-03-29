# plan.md — 433-zero-touch-agent-activation

## Summary
Build a first-party activation layer on top of the existing service and adapter foundation. Activation should own detection, managed surface installation, registry persistence, drift checks, and one-command repair while preserving the local-first and reversible design constraints from the existing runtime.

## Architecture impact
- touched components:
  - `opendream.activation`
  - `opendream.cli`
  - `opendream.service`
  - schema assets, docs, and tests
- unchanged components:
  - durable memory file formats
  - service supervisor rendering and worker semantics
  - retrieval, observability, and dream planner contracts

## Data model / contract changes
- add `agent-target`, `activation-report`, `managed-surface`, and `repair-report` schemas
- persist activation registry and reports under repo-local `.opendream/`
- manage target hook scripts, wrappers, and config blocks under actual agent-consumed paths
- keep `service autowire` as a compatibility alias backed by the activation layer

## Interfaces
- new CLI:
  - `opendream activate`
  - `opendream doctor --surface agents`
- existing CLI changed:
  - `opendream init --activate-configured`
  - `opendream service autowire`

## Security / safety review
- auth changes: none
- secret handling: unchanged; generated hooks only forward existing task and summary payloads
- irreversible actions: none; repair re-renders managed surfaces without deleting unrelated content
- new trust boundary: `.opendream/` becomes the inspectable managed-surface root for repo-local activation state

## Rollout
1. add canonical and proposal schema assets plus the active spec bundle
2. implement activation, detection, registry, and repair logic
3. wire CLI commands and compatibility aliases
4. add fixture-driven verification and release smoke
5. update README and adapter guidance to recommend activation as the standard path

## Rollback
1. remove the activation CLI and leave `service autowire` as the explicit manual path
2. stop reading `.opendream/agents.json` and ignore activation reports
3. retain generated hook scripts only as compatibility artifacts until they are manually removed

## Verification plan
- run: `./.venv/bin/python -m unittest tests.test_memory_cli -v`
- run: `./.venv/bin/python -m unittest tests.test_release_artifact -v`
- run: `./.venv/bin/python -m ruff check opendream tests scripts`
- run: `./.venv/bin/python -m mypy opendream scripts`
- run: `make verify`
- run: `make release-check`

## ADR needed?
- no
