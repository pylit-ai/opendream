# Architecture overview

## Purpose
Enduring technical structure of the system. Task-level implementation detail belongs in specs and plans.

## High-level components
- `opendream.cli` — operator-facing entrypoint for store initialization, event ingestion, extraction, dreaming, service lifecycle, retrieval, evaluation, contract export for agent integrations, and release-oriented verification hooks
- `opendream.storage` — filesystem-backed memory store, lock handling, custom memory-root routing, markdown generation, and audit artifact emission
- `opendream.extractor` — deterministic conversion from immutable events into typed memory candidates
- `opendream.bootstrap` — first-pass historical indexing that stages candidates and category inventory without durable apply
- `opendream.consolidator` — single-writer durable-memory maintenance, supersession, contradiction handling, decay, and startup-index generation
- `opendream.automation` — managed automation jobs that project typed, reviewable records from durable memory into a separate automation layer
- `opendream.dream` + `opendream.episodes` — transcript and log ingestion plus four-phase reflective dreaming
- `opendream.retriever` — hybrid retrieval with lexical, semantic, scope, recency, and type-aware scoring plus structured retrieval explanations
- `tests/fixtures/` + `tests/` — reproducible corpora and end-to-end verification harness for the subsystem

## Data flow
- events are appended as JSONL evidence under the configured memory root
- transcript or log episodes are narrowed into dream-worthy signal before event staging
- extraction produces typed candidates under `memory/state/candidates/`
- consolidation promotes candidates into durable records in `memory/state/durable_records.json`
- automation jobs read durable records and maintain projection outputs under `memory/automation/`
- durable records are rendered to `MEMORY.md`, topic markdown, and optional AutoDream compatibility views
- prompt context may include both durable memory and active automation projections, but they remain separate stores
- direct writes, dream runs, consolidation, retrieval, and release checks emit audit artifacts

## Boundaries
- no external network or database boundary in the default implementation
- consolidator writes are restricted to the workspace `memory/` subtree
- automation writes are restricted to the workspace `memory/automation/` subtree
- topic markdown is a generated user-editable representation of canonical durable state
- OpenSpec bundles remain proposal-stage; canonical implementation control lives in `specs/`

## Dependencies
- Python 3 standard library only
- repository OpenSpec schemas and config as the normative design reference

## Agent-ready platform (in progress)

Workstream `436-agent-ready-platform-complete` (OpenSpec change `openspec/changes/agent-ready-platform-complete/`) extends the architecture with:

- **Path-scoped guidance** — subtree `AGENTS.md` files plus root routing (`opendream/`, `openspec/`, `.meta/spec-adapters/`, `tests/`).
- **Contract export** — `opendream contract export` emits schema-validated JSON (`opendream/schema/contract-export.schema.json`) describing CLI commands, schema inventory, and version maps.
- **Distribution & engines (planned)** — thin vendor packages and an automation engine registry per ADR-003 and ADR-004.
- **Guidance drift & isolated execution (planned)** — proposal-only drift loop (ADR-006) and worktree-isolated code mutation (ADR-005).

## Out of scope for this doc
- Per-change rollout, file lists, and verification steps → `specs/<id>/plan.md`
- Product intent → `NORTHSTAR.md`, `PRD.md`
- Architectural decisions and rationale → `docs/adr/`
