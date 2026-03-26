# spec.md — 401-autodream-style-memory-subsystem

## Title
Implement the local-first memory subsystem for coding agents

## Why
The repo now contains a proposal-grade OpenSpec bundle for durable agent memory, but no executable runtime, fixtures, or verification harness. This change turns that design into a runnable local subsystem with deterministic file-backed behavior, an audit trail, and reproducible tests.

## In scope
- filesystem-backed memory store with append-only event and candidate capture
- bootstrap indexing, scheduled consolidation, retrieval, and demo CLI commands
- durable topic records, compact startup index generation, and audit artifacts
- deterministic tests and fixtures covering golden-run, bootstrap, contradiction, retrieval, and lock safety
- working `make setup`, `make test`, `make lint`, `make typecheck`, and `make verify`

## Out of scope
- external LLM integrations
- database-backed storage
- remote sync or cross-machine persistence

## User-visible behavior
- When an operator runs the CLI against a workspace, the system should create a memory store, append evidence, extract candidates, consolidate durable memory, and retrieve relevant records.
- When contradictory evidence arrives, the system should preserve provenance and mark or supersede records instead of silently overwriting them.
- When the consolidator runs, it should write only inside the memory store and emit audit artifacts.

## Acceptance criteria
- [x] AC-1: `python3 -m opendream_memory.cli demo --workspace <path>` produces `memory/MEMORY.md`, topic markdown files, candidate/event JSONL, and audit outputs in a deterministic local run.
- [x] AC-2: `python3 -m opendream_memory.cli bootstrap-index --workspace <path> --events <file>` produces category inventory and candidate artifacts without mutating durable topic memory before consolidation.
- [x] AC-3: `python3 -m opendream_memory.cli consolidate --workspace <path>` enforces single-writer locking and writes only inside the memory store.
- [x] AC-4: `python3 -m opendream_memory.cli retrieve --workspace <path> --query "<text>"` returns relevant durable memory with scores and emits retrieval audit output.
- [x] AC-5: `make verify` passes and includes automated coverage for deterministic consolidation, contradiction handling, bootstrap staging, retrieval, and concurrency safety.

## Edge cases
- stale lock files from interrupted runs
- low-confidence or sensitive events that should not be promoted
- superseding decisions with the same key but different bodies
- repeated workflow evidence that should only become durable after enough successful observations

## Required verifiers
- unit tests: yes, deterministic logic for extraction, consolidation, retrieval, and validation
- integration tests: yes, CLI end-to-end workflows on fixture corpora
- evals / scenario checks: yes, acceptance-style fixture flows for bootstrap and recurring workflows
- manual verification: yes, run `make verify` and `python3 -m opendream_memory.cli demo --workspace .tmp/demo`

## Risks
- markdown generation and durable state can drift if both are not produced from the same canonical records
- simplistic lexical retrieval can become noisy if scoring is not bounded and deterministic

## Links
- `../../openspec/changes/401-autodream-style-memory-subsystem/spec.md`
- `../../CONSTITUTION.md`
