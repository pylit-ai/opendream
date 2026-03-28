# spec.md — 414-memory-observability-read-model

## Title
Add a canonical observability read model for memory, runs, retrievals, and context assembly

## Why
OpenDream now has a local memory runtime, layered stores, and scheduler visibility, but humans still need a stable introspection surface that answers what exists, why it exists, and what changed during retrieval and consolidation. The source-of-truth artifacts already exist on disk; this change defines the typed read model that makes them queryable without mutating them.

## In scope
- typed schemas for `ContextAssembly`, `ConsolidationOp`, `Annotation`, `ReviewDecision`, and `PhaseTrace`
- indexed read-model tables or materialized JSON caches derived from source artifacts
- provenance-preserving backfill from memory files, audit logs, retrieval logs, and run outputs
- overview metrics for store health, lock state, recent sessions, recent runs, and memory counts
- stable IDs and cross-linking keys for memories, sessions, retrievals, runs, and annotations

## Out of scope
- HTTP or UI delivery surfaces
- review mutations beyond schema definitions
- graph visualization
- changing the underlying file-based source of truth

## User-visible behavior
- Operators can reconstruct current memory state from a typed read model rather than raw greps.
- A single consolidation run can be inspected as phase traces plus per-operation records.
- Retrieval and context assembly records preserve selected and omitted memory IDs, reasons, and assembled context payloads.
- Derived objects always point back to source artifact paths and object IDs.

## Acceptance criteria
- [x] AC-1: read-model schemas exist for `ContextAssembly`, `ConsolidationOp`, `Annotation`, `ReviewDecision`, and `PhaseTrace`
- [x] AC-2: a backfill command can index existing artifacts without mutating source memory files
- [x] AC-3: indexed records preserve provenance to source paths, run IDs, session IDs, and memory IDs where applicable
- [x] AC-4: broken or partial artifacts are tolerated and surfaced as warnings instead of crashing indexing
- [x] AC-5: overview aggregates expose current lock state, last run, recent sessions, recent runs, and counts by memory type and status

## Edge cases
- missing retrieval or consolidation audit files
- partial write artifacts from interrupted runs
- records that reference unknown memory IDs
- duplicate IDs across layered stores
- stores with zero historical runs

## Required verifiers
- unit tests: yes, schema validation and provenance preservation
- integration tests: yes, backfill over seeded artifacts and broken-artifact tolerance
- evals / scenario checks: no
- manual verification: yes, run the backfill/indexer against a seeded workspace and inspect the generated read model

## Risks
- the read model silently diverges from source artifacts
- provenance becomes lossy and blocks later explainability work
- overview metrics become misleading if derived state is stale

## Links
- `../../notepads/active/openspec_webapp_autodream_introspection_bundle.md`
- `../406-scheduler-and-status-surface/spec.md`
- `../405-layered-memory-stores/spec.md`
