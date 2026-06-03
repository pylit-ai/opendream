# Architecture overview

## Purpose
Enduring technical structure of the system. Task-level implementation detail belongs in issue threads, design notes, or change plans.

## Platform identity
OpenDream is a local-first memory control plane for agent-managed project workspaces. It stores typed canonical state, keeps contradiction and supersession relations explicit, and can connect deterministic local workflows with optional provider or agent-runtime integrations.

## High-level components
- `opendream.cli` — operator-facing entrypoint for store initialization, event ingestion, extraction, dreaming, service lifecycle, retrieval, evaluation, contract export for agent integrations, and release-oriented verification hooks
- `opendream.storage` — filesystem-backed memory store, lock handling, custom memory-root routing, markdown generation, and audit artifact emission
- `opendream.extractor` — deterministic conversion from immutable events into typed memory candidates
- `opendream.bootstrap` — first-pass historical indexing that stages candidates and category inventory without durable apply
- `opendream.consolidator` — single-writer durable-memory maintenance, supersession, contradiction handling, decay, and startup-index generation
- `opendream.automation` — managed automation jobs that project typed, reviewable records from durable memory into a separate automation layer
- `opendream.dream` + `opendream.episodes` — transcript and log ingestion plus four-phase reflective dreaming
- `/api/dream/cycles`, `/api/dream/funnel`, and `/api/dream/coverage` — read-only dream observability projections for phase timing, proposal yield, signal coverage, and deterministic cycle narratives
- `opendream.retriever` — hybrid retrieval with lexical, semantic, scope, recency, and type-aware scoring plus structured retrieval explanations
- `tests/fixtures/` + `tests/` — reproducible corpora and end-to-end verification harness for the subsystem

## Data flow
- events are appended as JSONL evidence under the configured memory root
- transcript or log episodes are narrowed into dream-worthy signal before event staging
- extraction produces typed candidates under `memory/state/candidates/`
- consolidation promotes candidates into durable records in `memory/state/durable_records.json`
- automation jobs read durable records and maintain projection outputs under `memory/automation/`
- durable records are rendered to `MEMORY.md`, topic markdown, and optional project/user compatibility views
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
- machine-readable contracts live under `opendream/schema/`

## Dependencies
- Python 3 standard library only
- machine-readable contracts under `opendream/schema/` as the packaged design reference

## Agent-ready platform (in progress)

The agent-ready platform work extends the architecture with:

- **Path-scoped guidance** — subtree `AGENTS.md` files plus root routing (`opendream/`, `.meta/spec-adapters/`, `tests/`).
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
- `opendream.benchmark_adapters`, `opendream.evaluation`, `opendream.harness_optimizer` — controlled fixtures, MemoryAgentBench-style adapters, coding-task evals, harness search
- Bundled third-party notices in `THIRD_PARTY_NOTICES.md`; benchmark provenance and clean-room boundaries in `docs/provenance.md`

### Semantic execution strategies (ADR-012)
Semantic mode runs are classified by execution strategy and auth source:

- **direct-provider**: OpenDream calls a model API using an explicit API key. Ingest is a direct run report.
- **codex-account**: OpenDream invokes Codex CLI as a local subprocess using the operator's ChatGPT account auth. Use only on a trusted local machine. Ingest is a direct run report.
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
- Opaque auth-token reuse from another tool is explicitly unsupported and never recommended
- Untrusted CI and shared runners never default to account-backed execution
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
- Checks memory-excellence evidence across direct-provider and delegated execution modes

## Out of scope for this doc
- Per-change rollout, file lists, and verification steps are maintained outside the runtime package.
- Product positioning and roadmap planning are outside this architecture overview.
- Architectural decisions and rationale → `docs/adr/`
