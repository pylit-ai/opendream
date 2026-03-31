# 01-plugin-distribution.md

## Goal
Make supported integrations installable and reproducible instead of copy-paste driven.

## Supported targets in this slice
- Codex plugin
- Claude Code plugin
- Cursor plugin
- GitHub Copilot instruction pack

## Design
### Canonical inputs
- root + path-scoped guidance
- adapter manifests
- selected skills
- MCP inventory entries
- package metadata file

### Generated outputs
- `dist/plugins/codex/<name>/...`
- `dist/plugins/claude-code/<name>/...`
- `dist/plugins/cursor/<name>/...`
- `dist/plugins/github-copilot/<name>/...`

### New CLI
- `opendream package scaffold --target <target>`
- `opendream package build --target <target> --workspace <ws>`
- `opendream package validate --path <package>`
- `opendream package smoke --target <target> --temp-repo`
- `opendream package manifest --target <target>`

### Required metadata
- package id
- version
- source commit / tree hash
- canonical source docs
- schema versions
- generated-at timestamp

## Safety
- generated packages must contain references back to canonical docs
- package generation must fail if required canonical inputs are missing
- generated files must be treated as derived artifacts
