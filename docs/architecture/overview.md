# Architecture overview

## Purpose
Enduring technical structure of the system. Task-level implementation detail belongs in specs and plans.

## High-level components
- `opendream_memory.cli` — operator-facing entrypoint for store initialization, event ingestion, extraction, bootstrap indexing, consolidation, retrieval, and demo runs
- `opendream_memory.storage` — filesystem-backed memory store, lock handling, markdown generation, and audit artifact emission
- `opendream_memory.extractor` — deterministic conversion from immutable events into typed memory candidates
- `opendream_memory.bootstrap` — first-pass historical indexing that stages candidates and category inventory without durable apply
- `opendream_memory.consolidator` — single-writer durable-memory maintenance, supersession, contradiction handling, decay, and startup-index generation
- `opendream_memory.retriever` — bounded lexical retrieval with task-aware type boosts and retrieval audit output
- `tests/fixtures/` + `tests/` — reproducible corpora and end-to-end verification harness for the subsystem

## Data flow
- events are appended as JSONL evidence under `memory/state/events/`
- extraction produces typed candidates under `memory/state/candidates/`
- consolidation promotes candidates into durable records in `memory/state/durable_records.json`
- durable records are rendered to `memory/MEMORY.md` and `memory/topics/*.md`
- consolidation and retrieval emit audit artifacts under `memory/audit/`

## Boundaries
- no external network or database boundary in the default implementation
- consolidator writes are restricted to the workspace `memory/` subtree
- topic markdown is a generated user-editable representation of canonical durable state
- OpenSpec bundles remain proposal-stage; canonical implementation control lives in `specs/`

## Dependencies
- Python 3 standard library only
- repository OpenSpec schemas and config as the normative design reference

## Out of scope for this doc
- Per-change rollout, file lists, and verification steps → `specs/<id>/plan.md`
- Product intent → `NORTHSTAR.md`, `PRD.md`
- Architectural decisions and rationale → `docs/adr/`
