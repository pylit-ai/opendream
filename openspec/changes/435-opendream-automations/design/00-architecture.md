# Architecture

OpenDream Automations sit beside the existing durable memory pipeline instead of inside it.

## Principles
- reuse `tick`, service, audit, and status machinery instead of inventing a second scheduler
- keep automation outputs in a separate typed store
- preserve provenance back to durable memories
- make top-level status and context additive, not conflated

## Initial slice
- job specs are local JSON documents under the memory root
- execution is deterministic and local-first
- records are merged or marked stale per job policy
- `prepare-context` surfaces active automation records in a dedicated section

## Deferred
- arbitrary `SKILL.md` or shell execution
- vendor-native automation adapters
- automation-driven product code edits
