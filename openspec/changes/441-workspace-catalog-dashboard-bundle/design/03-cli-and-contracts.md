# 03-cli-and-contracts.md

## CLI philosophy
Keep commands boring and explicit.

## New command family
- `opendream workspace list`
- `opendream workspace inspect`
- `opendream workspace scan`
- `opendream workspace roots list`
- `opendream workspace roots add`
- `opendream workspace roots remove`
- `opendream workspace forget`
- `opendream workspace doctor`

## Output contracts
All commands should support:
- human-readable default
- machine-readable `--format json` where existing conventions allow
- stable schemas for catalog and scan reports

## Error handling
Catalog failures should not corrupt workspace-local state.
Primary workspace commands may still succeed if catalog update fails, but the failure must be surfaced explicitly.
