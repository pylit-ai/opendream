# PRD

## Product
OpenDream

## Problem
Developers using coding agents on non-trivial repositories lose time and trust because the agent does not retain durable project memory in a reliable way. Transcript replay is too expensive, scratch notes decay into contradictory clutter, and opaque memory systems are hard to audit or correct. OpenDream exists to provide a local-first, typed, auditable memory subsystem that improves long-horizon agent performance without compromising operator control.

## Users
- Primary: developers running coding agents against active codebases
- Secondary: platform engineers integrating memory into agent runtimes or tooling

## Jobs to be done
- When a coding agent returns to a repository after time has passed, users want it to recover durable context quickly, so they can continue work without restating decisions, preferences, and environment constraints.
- When a project’s facts change, users want stale and conflicting memory handled explicitly, so the agent does not silently rely on outdated instructions.
- When a background maintenance pass runs, users want it to stay bounded and auditable, so the memory system improves itself without unexpectedly mutating product code.

## Scope
### In scope
- local filesystem-backed memory store with append-only evidence capture
- candidate extraction, bootstrap indexing, scheduled consolidation, and retrieval
- compact startup index, topic markdown files, and audit artifacts
- deterministic CLI demos, fixtures, and verification harnesses

### Out of scope
- external LLM orchestration inside the memory subsystem
- cloud sync, hosted multi-user collaboration, or remote persistence by default

## User stories
1. As a developer, I want durable memory for project decisions, workflows, and environment requirements, so that my coding agent stops forgetting critical context.
2. As an operator, I want every durable mutation to be explainable from source evidence, so that I can trust and debug the memory system.
3. As a platform builder, I want a clean-room, portable implementation surface, so that I can embed the subsystem without inheriting opaque third-party code.

## Functional requirements
- FR-1: The system must capture immutable memory events and derive typed memory candidates without directly mutating durable memory.
- FR-2: The system must consolidate durable memory through a single-writer path that preserves provenance, handles contradiction explicitly, and keeps startup memory compact.
- FR-3: The system must expose CLI commands and reproducible tests for initialization, event ingestion, bootstrap indexing, consolidation, retrieval, and demo workflows.

## Non-functional requirements
- NFR-1: Startup memory generation and retrieval must remain bounded and deterministic on fixture corpora.
- NFR-2: The default implementation must be local-first, avoid remote persistence, and refuse to promote sensitive values into durable memory.
- NFR-3: Every durable write path must emit audit artifacts sufficient to diagnose state changes without reading prompts.

## Success metrics
- `make verify` stays green with deterministic fixture-driven tests
- repeated-task retrieval returns the expected project preferences, workflows, and environment requirements in top results
- durable memory mutations can be traced from source events to topic files and startup index output

## Failure modes to design against
- silent overwrite of contradictory evidence
- memory maintenance writing outside the intended `memory/` subtree
- startup index bloat that turns durable memory back into a transcript dump
- promotion of secrets or noisy low-confidence facts into durable memory

## Dependencies
- Python 3 standard library runtime
- local filesystem access for the workspace memory store
- canonical repo specs, OpenSpec bundle, and schema files for design control

## Open questions
- should lexical retrieval remain the default long-term, or should embeddings become an optional adapter once the deterministic baseline is stable?
- when the system graduates beyond single-repo local usage, what replication model preserves the same auditability and trust properties?
