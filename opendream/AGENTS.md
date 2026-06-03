# OpenDream runtime — agents

## Purpose

Path-scoped guidance for the `opendream/` Python package (CLI implementation, memory runtime, activation, automation). Root `AGENTS.md` routes here when changing runtime behavior.

## Read order

1. `docs/architecture/overview.md`
2. `docs/adr/` for durable architecture decisions
3. JSON schemas under `opendream/schema/` for machine-readable contracts
4. `docs/architecture/overview.md` for invariants

## Conventions

- Prefer **minimal diffs**; match existing module patterns (`cli.py` dispatches to command handlers).
- New **stable JSON outputs** must be documented in `opendream contract export` and covered by schema + fixtures when applicable.
- **Stdlib-only** runtime: no new required third-party dependencies in core paths without an explicit spec and ADR.

## Contract export

- Command: `opendream contract export --workspace <path> --format json`
- Schema: `opendream/schema/contract-export.schema.json`
- Contract export: top-level **`cli_output_version`** tracks **`CLI_JSON_VERSION`** (same integer as other command JSON). Bump **`CONTRACT_EXPORT_DOCUMENT_VERSION`** / **`output_version_map.contract_export`** when the export document shape changes.
