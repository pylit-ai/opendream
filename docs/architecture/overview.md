# Architecture overview

## Purpose
Enduring technical structure of the system. Task-level implementation detail belongs in specs and plans.

## Platform identity
OpenDream is a **verified, bounded, relation-aware memory control plane** that accepts semantic work from multiple execution owners (direct-provider, Codex, Claude, Cursor, deterministic). It is not a note folder, a single-vendor wrapper, or a memory-agent monoculture. It exceeds note-oriented memory systems by offering typed canonical state, verify-before-assert patterns, contradiction/supersession relations, procedural memory, generated-only views, release scorecards, and cross-runtime execution support.

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

## Machine-local workspace catalog
- `opendream.workspace_catalog` maintains a **derived, machine-local** index of OpenDream workspaces at `~/.opendream/catalog.json` plus explicit scan roots at `~/.opendream/roots.json` (override via `OPENDREAM_CATALOG_HOME`)
- the catalog is **never canonical**: per-workspace `.opendream/` state remains the source of truth and the catalog can be rebuilt from it via `workspace scan`
- updates are event-driven (successful `init`/`activate`/`install-service`) or explicit (`workspace scan --root <path>` / `--all-roots`) — there is no default whole-home crawl, background discovery, or remote sync
- the CLI surfaces `workspace list/inspect/scan/roots/forget/doctor` and the local web UI exposes `/workspaces` backed by the same index; both must agree on naming and status kinds (`ok|stale|missing|broken`)
- catalog failures are surfaced explicitly via the `catalog_update` block in primary-command results; they never corrupt workspace-local state
- rationale: [`docs/adr/ADR-017-machine-local-workspace-catalog.md`](../adr/ADR-017-machine-local-workspace-catalog.md)

## Boundaries
- no external database; **default deterministic** consolidation and automation paths do not open network connections from this package
- optional semantic **provider** configuration is on-disk (`state/provider_registry.json`) for health checks and future vendor transports; current synthesis/verification paths remain in-process heuristics (see `opendream/semantic_dreamer.py`, `opendream/semantic_verifier.py`)
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

## Semantic sleep-time compute

The semantic dreamer (`opendream.semantic_dreamer`) extends dreaming with a learned-context pipeline configured via `state/semantic_config.json` and `state/provider_registry.json`. **Operator setup:** [docs/automation/semantic-mode-and-feature-radar-setup.md](../automation/semantic-mode-and-feature-radar-setup.md). **Command-order cookbook and LLM vs heuristic boundaries:** [docs/automation/complete-operator-workflow.md](../automation/complete-operator-workflow.md).

### Learned-context layer (ADR-007)
- Learned-context **records** persist via `opendream.storage` (`state/learned_context_records.json`, related topic paths)
- Separate from canonical durable records; independent freshness TTL and staleness policy
- Records carry provenance metadata (source events, provider/model identifiers, prompt version)

### Semantic verifier and promotion (ADR-008)
- `opendream.semantic_verifier` — deterministic and heuristic semantic checks on proposals before promotion
- Promotion integrates with the learned-context store; durable vs learned retrieval weighting follows ADR-009 in `opendream.retriever`

### Hybrid retrieval extensions (ADR-009)
- `opendream.retriever` applies source-type weighting and gating between durable facts and learned context
- Per-source attribution and harm-aware suppression for learned-context records

### Benchmark suite and harness optimizer (ADR-010, ADR-011)
- `opendream.benchmark_adapters`, `opendream.evaluation`, `opendream.harness_optimizer` — internal fixtures, MemoryAgentBench-style adapters, coding-task evals, harness search
- Third-party provenance in `THIRD_PARTY_NOTICES.md`; benchmark protocols reimplemented clean-room where applicable

### Semantic execution strategies (ADR-012)
Semantic mode runs are classified by execution strategy and auth source:

- **direct-provider**: OpenDream calls a model API using an explicit API key. Ingest is a direct run report.
- **codex-account**: OpenDream invokes Codex CLI as a local subprocess using the operator's ChatGPT account auth. Trusted local/private infrastructure only. Ingest is a direct run report.
- **claude-scheduled-task**: Claude runs a scheduled task or command/skill. Results return via a delegated semantic envelope into `.opendream/inbox/semantic/claude-scheduled-task/`. Ingest is validated envelope-based.
- **cursor-automation**: A Cursor automation writes a semantic envelope artifact into the repo. Results return via `.opendream/inbox/semantic/cursor-automation/`. Ingest is validated envelope-based.
- **deterministic**: No model call. Always available as a fallback.

The setup wizard (`opendream semantic setup`) resolves a single recommended strategy. `--prefer no-extra-key` (default) prefers vendor-account-backed paths; `--prefer direct-provider` prefers explicit API keys.

### Delegated semantic ingest (ADR-013)
- Vendor-delegated runs write structured envelopes to `.opendream/inbox/semantic/<adapter>/`
- `opendream semantic ingest` validates envelopes against schema before converting to proposals
- Invalid envelopes are archived, never silently applied
- Accepted proposals enter the same verify-promote pipeline as direct runs

### Unsupported paths
- Gemini CLI OAuth reuse is explicitly unsupported and never recommended
- Public/untrusted runners never default to account-backed execution
- Arbitrary vendor OAuth session borrowing is forbidden

### Feature mining and radar integration
- `automation scaffold-dream` generates adapter-specific job specs for feature-radar, bug-radar, fix-radar, and semantic-refresh
- Layer A (durable capture) and Layer B (deterministic projection) are always local
- Layer C (semantic refresh/reconciliation) can be delegated to vendor runtimes via adapter scaffolds
- Projections from mining and radar remain non-canonical until promoted through the standard pipeline

### Advanced runtime proof (ADR-016)
- The advanced-runtime report (`advanced-runtime-report.schema.json`) combines memory-excellence scorecard results, execution-mode test coverage, and docs truthfulness checks
- Generated during `make release-check` and archived alongside release artifacts
- Release verdict (`pass`, `fail`, `partial`) gates the release — `fail` blocks shipping
- Proves that memory-excellence guarantees hold across direct-provider and delegated execution modes

## Out of scope for this doc
- Per-change rollout, file lists, and verification steps → `specs/<id>/plan.md`
- Product intent → `NORTHSTAR.md`, `PRD.md`
- Architectural decisions and rationale → `docs/adr/`
