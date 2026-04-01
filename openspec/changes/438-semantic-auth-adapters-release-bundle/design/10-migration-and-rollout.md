# 10-migration-and-rollout.md

## Migration principles
- existing direct-provider and deterministic semantic config continue to work
- existing docs and release notes must be reconciled as part of the same change
- existing `437` semantic commands remain, but their semantics become explicit through the new policy/status layer

## Rollout order
1. schemas + status fields + setup report
2. setup wizard and detection logic
3. Codex adapter
4. Claude adapter
5. Cursor adapter
6. delegated envelope ingest
7. docs and release notes
8. release gates

## Compatibility
- if a workspace already has semantic config, setup uses it as an input rather than overwriting blindly
- adapters are additive
- direct-provider remains available everywhere it already worked
