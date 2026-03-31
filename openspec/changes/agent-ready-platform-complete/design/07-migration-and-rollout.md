# 07-migration-and-rollout.md

## Migration principles
- no breaking change to existing `435` jobs
- package generation is additive
- engine registry can admit a compatibility path for current deterministic built-ins
- root docs remain canonical and human-readable

## Rollout order
1. contracts + nested guidance
2. MCP inventory + conformance checks
3. package generation
4. engine registry
5. guidance-drift built-ins
6. isolated worktree execution
7. full release gates

## Compatibility
- existing adapter manifests continue to work
- current `skill_ref` values that map to built-ins can be auto-migrated to canonical built-in ids
- undocumented third-party refs become warnings first, then errors behind a migration flag

## Docs
- update README and architecture docs
- add migration notes for operators using current `.meta/spec-adapters/*`
- add package generation quickstarts for each vendor
