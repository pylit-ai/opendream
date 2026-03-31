# OpenDream runtime — agents

## Purpose

Path-scoped guidance for the `opendream/` Python package (CLI implementation, memory runtime, activation, automation). Root `AGENTS.md` routes here when changing runtime behavior.

## Read order

1. `docs/architecture/overview.md`
2. Active spec in `specs/<id>/` and `specs/registry.yaml`
3. `CONSTITUTION.md` for invariants
4. JSON schemas under `opendream/schema/` for machine-readable contracts

## Conventions

- Prefer **minimal diffs**; match existing module patterns (`cli.py` dispatches to command handlers).
- New **stable JSON outputs** must be documented in `opendream contract export` and covered by schema + fixtures when applicable.
- **Stdlib-only** runtime: no new required third-party dependencies in core paths without an explicit spec and ADR.

## Contract export

- Command: `opendream contract export --workspace <path> --format json`
- Schema: `opendream/schema/contract-export.schema.json`
- Bump `cli_output_version` inside the export payload when the shape changes.
