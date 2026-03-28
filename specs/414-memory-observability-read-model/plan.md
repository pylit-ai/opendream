# plan.md — 414-memory-observability-read-model

## Summary
Build a typed, provenance-preserving read model on top of the existing filesystem artifacts. Keep files as the source of truth and treat the read model as an indexed projection for observability, filtering, and later API delivery.

## Architecture impact
- touched components:
  - `opendream_memory.models`
  - storage and audit artifact readers
  - new read-model indexer or cache builder
  - tests and fixtures
- unchanged components:
  - canonical memory file layout
  - runtime mutation behavior
  - CLI behavior unrelated to indexing

## Data model / contract changes
- add typed contracts for:
  - `ContextAssembly`
  - `ConsolidationOp`
  - `Annotation`
  - `ReviewDecision`
  - `PhaseTrace`
- add overview aggregate contract for counts, lock state, and recent activity
- preserve source path, source object ID, and run/session references on every derived record

## Interfaces
- new index/backfill command:
  - `opendream-memory index-observability --workspace <path>`
- optional output modes:
  - materialized JSON cache under the memory root
  - SQLite-backed read model for later APIs

## Read-model rules
- source files remain canonical
- the indexer must never mutate memory artifacts
- every derived row or document stores provenance
- indexing must be idempotent over the same artifact set
- broken artifacts are reported and skipped, not silently repaired

## Rollout
1. add spec and registry entry
2. define schemas and provenance contract
3. implement backfill/indexer
4. add aggregate queries and fixtures
5. rerun verification

## Rollback
1. remove the indexer and derived caches
2. keep source artifacts and existing runtime unchanged

## Verification plan
- run: `make test`
- manual checks:
  - seed a workspace with events, retrieval logs, and consolidation outputs
  - run the indexer twice and confirm stable output
  - inject a broken artifact and confirm warning-plus-continue behavior

## ADR needed?
- no
