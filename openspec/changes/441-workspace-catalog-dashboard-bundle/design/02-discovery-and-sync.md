# 02-discovery-and-sync.md

## Discovery sources
1. event-driven updates on:
   - `init`
   - `activate`
   - `install-service`
   - optionally `status` and `service status`
2. explicit root scans:
   - `workspace scan --root <path>`
   - `workspace scan --all-roots`

## Root-scan policy
- roots are explicit and persisted in `roots.json`
- no default scan of `$HOME`
- no background crawl without operator action

## Probe policy
Dashboard and `workspace doctor` may probe entries lazily for:
- path exists?
- `.opendream/` exists?
- `targets.json` present?
- `activation-state.json` present?
- service manifest/report present?
- memory root present?

Probe results update cache fields, not canonical workspace state.
