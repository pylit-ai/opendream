# plan.md — 441-workspace-catalog-dashboard-bundle

## Summary

Implement a machine-local workspace catalog and dashboard that index known OpenDream workspaces while preserving the current workspace-scoped storage model. The catalog is derived from explicit roots and workspace-local `.opendream/` metadata; it is never authoritative over the workspace itself.

## Product fit

### Aligns with North Star
Yes.
The North Star explicitly targets a local-first memory substrate used across multiple repos and runtimes. A central workspace catalog improves multi-repo operator ergonomics and makes OpenDream feel like a coherent substrate rather than a pile of repo-local state.

### Aligns with Constitution
Yes, with constraints.
The Constitution favors:
- local-first inspectable behavior
- operator control
- structured observability
- no hidden remote state
- no silent fallbacks

This feature aligns if:
- the catalog is machine-local and inspectable,
- the catalog is derived and repairable,
- root scanning is explicit/opt-in,
- state transitions are logged,
- failures are visible,
- and per-workspace `.opendream/` state remains canonical.

## Architecture impact

### Touched components
- `opendream/cli.py`
- `opendream/webapp.py`
- `opendream/activation.py`
- `opendream/service.py`
- `opendream/storage.py`
- `opendream/validation.py`
- `opendream/models.py`
- `opendream/observability.py`
- `opendream/contract_export.py` (if command surfaces/JSON contracts are extended)
- `README.md`
- `docs/FAQ.md`
- `docs/architecture/overview.md`
- `docs/coding-agents.md`
- tests and fixtures

### New modules expected
- `opendream/workspace_catalog.py`
- `opendream/workspace_probe.py`
- `opendream/workspace_dashboard.py` (or dashboard handlers in `webapp.py`)

### New persisted artifacts expected
Machine-local, operator-visible catalog state:
- `~/.opendream/catalog.json`
- `~/.opendream/roots.json`
- optional cached probe state:
  - `~/.opendream/catalog-cache.json`

These paths should be configurable later, but a simple home-based default is acceptable for v1.

## Data model / contract changes
- add workspace catalog schema
- add scan roots schema
- add workspace dashboard card/status schema
- add scan report schema
- extend status/read-model payloads as needed for UI aggregation

## Interfaces

### New CLI
- `opendream workspace list`
- `opendream workspace inspect --workspace <path>|--entry-id <id>`
- `opendream workspace scan [--root <path>] [--all-roots]`
- `opendream workspace roots list`
- `opendream workspace roots add --path <root>`
- `opendream workspace roots remove --path <root>`
- `opendream workspace forget --workspace <path>`
- `opendream workspace doctor [--workspace <path>|--all]`

### UI
- add `/workspaces` dashboard route
- add workspace detail navigation from dashboard cards into existing workspace-scoped views

## Observability
- catalog updates emit structured logs
- scans emit machine-readable reports
- dashboard probes expose stale/missing/broken states
- catalog update failures do not silently disappear

## Security / safety review
- scanning must be opt-in by root
- no automatic full-disk traversal
- no remote sync
- no secrets or sensitive values promoted into the catalog
- catalog entries should contain only bounded operator-facing metadata

## Rollout
1. land schemas and machine-local catalog storage
2. land CLI list/scan/roots commands
3. land event-driven catalog updates on init/activate/install-service
4. land dashboard route and cards
5. land docs and FAQ updates
6. land release gates and tests

## Rollback
1. disable dashboard route
2. stop updating the machine-local catalog
3. keep workspace-local `.opendream/` state untouched
4. retain catalog files for operator inspection or manual cleanup

## Verification plan
- unit tests for catalog merge/update rules
- unit tests for root scan filtering and stale-entry handling
- integration tests for CLI commands
- integration tests for dashboard rendering and probe states
- `make verify` includes catalog/dashboard tests

## ADR needed?
Yes.
Document:
- why a machine-local catalog is allowed under the Constitution
- why it is derived rather than canonical
- why root scans are opt-in
