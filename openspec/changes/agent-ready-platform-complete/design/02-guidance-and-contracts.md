# 02-guidance-and-contracts.md

## Goal
Give agents the minimum durable context they need, at the closest useful scope, with a stable contract for machine clients.

## Guidance model
### Layers
1. root `AGENTS.md`
2. subtree guidance files for:
   - `opendream/`
   - `openspec/`
   - `.meta/spec-adapters/`
   - `tests/`
3. generated vendor instruction outputs derived from those files

### Rules
- path-scoped guidance may specialize, not fork governance
- root guidance remains routing-oriented
- no adapter file may become a hidden policy source

## Contract model
### New command
- `opendream contract export --workspace <ws> --format json`

### Contract contents
- command index
- schema inventory
- stable JSON field inventory
- output version map
- example payloads and hashes
- deprecation signals
- supported package targets
- supported engine ids

### Fixtures
- add generated JSON fixtures under `opendream/fixtures/contracts/`
- tests must compare exported contracts against fixtures or snapshots
