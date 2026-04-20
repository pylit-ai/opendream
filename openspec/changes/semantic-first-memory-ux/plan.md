# plan.md — 443-semantic-first-memory-ux

## Summary

Add a follow-on product layer on top of the existing semantic execution and observability work so OpenDream behaves like a semantic-first memory product rather than a deterministic store with an optional semantic label. The core implementation focus is truthful readiness, progressive context disclosure, visible pruning, and operator-grade quality diagnostics across CLI and web UI.

## Architecture impact

### Touched components
- `opendream/cli.py`
- `opendream/semantic_setup.py`
- `opendream/provider_registry.py`
- `opendream/integration.py`
- `opendream/observability.py`
- `opendream/contract_export.py`
- `opendream/webapp.py`
- `opendream/static/observe-ui.js`
- `opendream/schema/` contract assets for readiness and quality reporting
- `scripts/release_check.py`
- benchmark/eval fixtures and tests
- docs/playbooks/FAQ/README benchmark and observe sections

### Unchanged components
- canonical durable record schema and provenance model
- delegated envelope trust boundary
- health live-check probe behavior introduced by `442`
- generated-view rule that `MEMORY.md` remains a view, not canonical state

## Data model / contract changes

- extend top-level status, overview, and contract export with:
  - `product_posture`
  - `semantic_capability_state`
  - `semantic_unavailability_reason`
  - `memory_quality`
  - `context_pruning`
- extend `prepare-context` JSON output with profile, budget, suppression, and pruning metadata
- add machine-readable reports or schema fixtures for:
  - memory quality
  - context selection / pruning evidence
  - semantic readiness summary if existing setup/status contracts are insufficient

## Interfaces

### Existing CLI changed
- `opendream init --workspace <path> --activate-configured`
- `opendream activate --workspace <path>`
- `opendream status --workspace <path>`
- `opendream workspace doctor --workspace <path>`
- `opendream semantic status --workspace <path>`
- `opendream prepare-context --workspace <path>`
- `opendream contract export --workspace <path> --format json`

### Existing observe API/UI changed
- `/api/overview`
- `/api/health` linkouts and overview composition
- `/overview`
- `/settings`

## Security / safety review

- no new auth reuse is introduced
- semantic-first posture MUST remain truthful about actual execution ownership
- degraded fallback MUST stay explicit everywhere user-facing state is summarized
- pruning/reporting MUST NOT hide raw evidence or silently drop inspectability
- no new background path may mutate product code or bypass existing memory-integrity constraints

## Rollout

1. add registry entry and proposal bundle
2. land contract/read-model additions for readiness and quality
3. land progressive context profiles and pruning metadata
4. land memory-quality diagnostics and homogeneous-workspace fixture
5. land web UI readiness/settings/context-preview changes
6. land docs/playbook/FAQ updates
7. land release gates for context-efficiency and semantic-first truthfulness

## Rollback

1. remove semantic-first UI/CLI posture layer
2. preserve existing semantic setup/status behavior from `440`
3. keep health contract from `442`
4. keep memory-quality internals or reports behind advanced surfaces if partial rollback is needed

## Verification plan

- targeted unit tests for readiness-state derivation, memory-quality heuristics, and context-profile selection
- targeted integration tests for `status`, `workspace doctor`, `prepare-context`, `/api/overview`, and `/settings`
- benchmark fixture tests for homogeneous-memory, semantic-ready, and deterministic-by-choice workspaces
- `make verify`
- `make release-check`

## ADR needed?

- yes

This bundle introduces a durable product contract for semantic-first posture and progressive context budgeting, so the enduring decision should be promoted if the implementation lands.
