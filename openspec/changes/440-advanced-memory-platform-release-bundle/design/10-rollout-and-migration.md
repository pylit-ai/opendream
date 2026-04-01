# 10-rollout-and-migration.md

## Dependencies
- memory-excellence bundle active
- current semantic mode / provider registry / benchmark adapters remain intact
- current thin adapter governance remains intact

## Rollout order
1. schemas and execution-policy fields
2. setup wizard and status surfaces
3. Codex adapter
4. Claude adapter
5. Cursor adapter
6. delegated envelope ingest
7. feature-mining/radar scaffolds
8. docs and release-note reconciliation
9. advanced-runtime report and gates

## Migration
- existing direct-provider users continue to work
- existing deterministic users continue to work
- existing thin hooks remain valid, but setup wizard now recommends stronger surface-specific paths when present
