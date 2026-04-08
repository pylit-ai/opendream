# 01-catalog-model.md

## Canonical rule
The global catalog is a convenience index.
The workspace remains the source of truth.

## Suggested files
- `~/.opendream/catalog.json`
- `~/.opendream/roots.json`
- optional `~/.opendream/catalog-cache.json`

## Catalog entry fields
- `workspace_path`
- `workspace_name`
- `repo_root_name`
- `first_seen_at`
- `last_seen_at`
- `discovered_by` (`init`, `activate`, `scan`, `install-service`, `manual-add`)
- `memory_dir`
- `activation_state_summary`
- `service_state_summary`
- `semantic_state_summary`
- `last_probe_at`
- `status_kind` (`ok`, `stale`, `missing`, `broken`)
- `notes` / remediation hints

## Why not canonical
Because a workspace can be moved, deleted, repaired, or manually modified without touching the catalog.
If the catalog became canonical, it would violate the current local-first workspace-scoped model and create harder-to-debug drift.
