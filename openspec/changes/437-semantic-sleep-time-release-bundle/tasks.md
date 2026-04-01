# tasks.md — 437-semantic-sleep-time-release-bundle

## Rules
- Execute in dependency order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.
- This bundle is not done until the release gates pass and docs no longer describe semantic mode as absent.

## WS1 — Canonical registration and architecture
- [x] T1: add `437-semantic-sleep-time-release-bundle` to `specs/registry.yaml` with dependencies on `418`, `430`, `435`, `436`, and `420`
- [x] T2: add ADRs for semantic learned context, verifier/promotion, benchmark architecture, and provenance policy
- [x] T3: update `docs/architecture/overview.md` to include semantic dreamer, learned context, benchmark suite, and harness optimizer
- [x] T4: update `README.md` and `docs/FAQ.md` to remove "no model-backed consolidation" language and replace it with truthful hybrid-mode docs

## WS2 — Schemas, storage, and contracts
- [x] T5: add schemas for learned-context records, semantic config, semantic dream reports, benchmark runs, and harness optimization reports
- [x] T6: add storage model and validation plumbing for learned-context records and semantic audit artifacts
- [x] T7: extend contract export with semantic mode commands, schemas, providers, and benchmark surfaces
- [x] T8: add fixtures / snapshots for contract export and new schema objects
- [x] T9 [P]: add generated human-facing learned-context topic/export views and ensure they remain derived artifacts

## WS3 — Provider registry and model roles
- [x] T10: implement provider/model registry with health checks
- [x] T11: add config loading for semantic mode, budgets, model roles, and fallback policy
- [x] T12: implement structured-output / parse-validation contracts for anticipation, synthesis, and semantic verification
- [x] T13: add CLI inspection commands for semantic config and provider health
- [x] T14: add tests for missing credentials, bad provider ids, malformed structured outputs, and fallback policy

## WS4 — Query-family anticipation planner
- [x] T15: implement query-family models and storage
- [x] T16: implement query-family inference from transcripts, retrieval logs, and task traces
- [x] T17: add static family manifests and operator allow/deny lists
- [x] T18: implement ranking and budget-aware truncation of query families
- [x] T19: extend dream reports to include selected families and planning rationale
- [x] T20: add deterministic tests for clustering, ranking, truncation, and manifest merging

## WS5 — Semantic dreamer core
- [x] T21: add `semantic_dreamer.py` and integrate it into DreamRunner
- [x] T22: implement semantic run phases: infer-families -> synthesize -> verify -> promote/archive
- [x] T23: support deterministic, semantic, and hybrid run modes in `dream run|tick|worker|daemon`
- [x] T24: add cost/token budget enforcement and early exit behavior
- [x] T25: extend `dream status` with semantic mode metadata
- [x] T26: add transcript-only integration tests for semantic and hybrid runs
- [x] T27 [P]: add queue-backed semantic worker coverage and worker-state observability

## WS6 — Semantic verifier and promotion
- [x] T28: add deterministic verifier checks for semantic outputs
- [x] T29: add semantic verifier role and output contract
- [x] T30: implement proposal-only default and explicit promotion state machine
- [x] T31: add optional distillation from learned context into typed durable candidates
- [x] T32: add conflict handling between learned context and durable facts
- [x] T33: add review / reject / supersede flows with audit trails
- [x] T34: add integration tests for veto, downgrade, acceptance, distillation, and rollback

## WS7 — Retrieval fusion and context injection
- [x] T35: extend retrieval scoring to consider learned-context records with source attribution and freshness
- [x] T36: implement source-aware fusion across durable/procedural/learned/projection memory
- [x] T37: extend `prepare-context` output with per-source selected ids and attribution
- [x] T38: add harm-aware suppression of stale or contradicted learned context
- [x] T39: add tests for fusion ranking, attribution, freshness penalties, and suppression
- [x] T40 [P]: update webapp / observability surfaces to display learned-context selection and harm signals

## WS8 — Semantic automations
- [x] T41: extend automation engine/registry to admit semantic refresh / strategist jobs
- [x] T42: add job specs and docs for semantic refresh over feature/fix/bug radar
- [x] T43: implement strategist job surfaces that use learned context without treating projections as canonical truth
- [x] T44: add automation integration tests for semantic refresh and strategist jobs
- [x] T45: update docs/automation playbooks for semantic refresh setup and review

## WS9 — Benchmark suite (internal + MemoryAgentBench-style)
- [x] T46: add internal semantic benchmark fixtures covering query-family anticipation, stale abstractions, conflict cases, and memory-hurt
- [x] T47: implement unified benchmark runner for deterministic-only / semantic-only / hybrid
- [x] T48: add machine-readable benchmark run report schema and artifact writer
- [x] T49: implement AR adapter
- [x] T50: implement TTL adapter
- [x] T51: implement LRU adapter
- [x] T52: implement CR adapter
- [x] T53: build clean-room MemoryAgentBench compatibility loader and scorer
- [x] T54: add benchmark docs describing benchmark philosophy, competencies, and limitations
- [x] T55: add benchmark tests and smoke runs

## WS10 — Coding-task evals and memory-hurt accounting
- [x] T56: define repeated coding-task eval corpus and task harness
- [x] T57: implement utility metrics: pass rate, success@cost, success@latency, irrelevant recall, contradiction recovery, procedural reuse
- [x] T58: implement memory-hurt event schema and attribution logic
- [x] T59: add deterministic vs semantic vs hybrid coding-task ablations
- [x] T60: integrate coding-task evals into release evidence
- [x] T61: add tests and docs for memory-hurt attribution

## WS11 — Meta-harness bootstrap and optimization
- [x] T62: implement environment bootstrap capture for coding-agent contexts
- [x] T63: expose bootstrap outputs in agent-ready context surfaces and docs
- [x] T64: implement harness optimizer scaffolding with proposal/eval/report contracts
- [x] T65: define search spaces for memory injection, retrieval policy, query-family selection, and semantic prompts
- [x] T66: implement toy optimization workflow and schema-valid reports
- [x] T67: add smoke tests and docs; ensure optimization results remain proposal-only
- [x] T68: add ablation docs explaining when bootstrap/optimizer should be enabled

## WS12 — Provenance, licensing, and release docs
- [x] T69: add `THIRD_PARTY_NOTICES.md` and copied-source inventory format
- [x] T70: record MIT provenance and notice handling rules for Sleep-time Compute reuse
- [x] T71: record clean-room adapter policy for MemoryAgentBench and Meta-Harness unless explicit licenses are confirmed
- [x] T72: add release-check conformance for provenance / notice files
- [x] T73: update README, FAQ, benchmark docs, and skeptical-engineer documentation for semantic mode, benchmark honesty, and fallback behavior

## WS13 — Release gates and package truthfulness
- [x] T74: extend `scripts/verify.py` with semantic benchmark and release-blocker stages
- [x] T75: extend `scripts/release_check.py` to archive semantic benchmark outputs, coding-task evals, and provenance manifest
- [x] T76: add package smoke tests and contract-export validation for semantic commands
- [x] T77: add release thresholds and failure reporting
- [x] T78: add full manual release matrix and evidence checklist
- [x] T79: reconcile all acceptance criteria and update registry statuses

## Parallelizable
- [x] [P] TP1: schemas/contracts work can proceed in parallel with docs updates
- [x] [P] TP2: benchmark adapters can proceed in parallel once run-report schema lands
- [x] [P] TP3: harness bootstrap work can proceed in parallel with semantic dreamer core
- [x] [P] TP4: provenance/docs updates can proceed in parallel with implementation once policy is decided

## Required verification commands
- [x] V1: unit tests for schemas, provider registry, query-family inference, verifier logic, retrieval fusion, and harm accounting
- [x] V2: integration tests for semantic dream runs, promotion, automations, benchmark runners, and bootstrap surfaces
- [x] V3: `./.venv/bin/python -m ruff check opendream tests scripts`
- [x] V4: `./.venv/bin/python -m mypy opendream scripts`
- [x] V5: `make verify`
- [x] V6: `make release-check`
- [x] V7: benchmark smoke for internal suite, MAB-style suite, and coding-task eval suite
- [x] V8: package / contract smoke for semantic commands and exports

## Completion checklist
- [x] semantic mode implemented and documented
- [x] learned-context layer exists and is auditable
- [x] query-family anticipation exists
- [x] verifier / promotion contracts exist
- [x] retrieval fusion with attribution exists
- [x] benchmark suite exists and passes
- [x] coding-task evals and memory-hurt accounting exist
- [x] meta-harness bootstrap/optimizer surfaces exist
- [x] provenance and notice files are complete
- [x] release gates pass
- [x] no further semantic-mode engineering changes are required before release
