# tasks.md — 439-memory-excellence-release-bundle

## Rules
- Execute in dependency order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.
- This bundle is not done until release gates pass and docs reflect the shipped runtime.

## WS1 — Canonical registration and architecture
- [ ] T1: add `439-memory-excellence-release-bundle` to `specs/registry.yaml` with explicit dependencies on existing memory/runtime specs
- [ ] T2: add ADRs for enforced maintenance boundaries, verified writes, generated-only views, contradiction graph semantics, and reconciliation sweeps
- [ ] T3: update `docs/architecture/overview.md` to reflect memory-excellence architecture and generated-view discipline

## WS2 — Schemas and contracts
- [x] T4: add `relation-edge.schema.json`
- [x] T5: add `claim-verification-report.schema.json`
- [x] T6: add `transcript-probe-report.schema.json`
- [x] T7: add `reconciliation-report.schema.json`
- [x] T8: add `memory-excellence-scorecard.schema.json`
- [x] T9: extend contract export with new reports, commands, and scorecard surfaces
- [x] T10: add schema fixtures and validation coverage

## WS3 — Enforced runtime boundaries
- [x] T11: implement runtime path allowlist enforcement for dream worker
- [x] T12: implement runtime path allowlist enforcement for semantic worker or future semantic path if not yet present
- [x] T13: add explicit boundary-violation reports
- [x] T14: add no-code-write diff verifier integration
- [x] T15: add unit/integration tests for blocked writes and allowed writes

## WS4 — Verify-before-assert and provenance tiers
- [x] T16: define concrete claim classes and provenance-tier model in runtime code
- [x] T17: implement claim classifier for externally checkable vs abstraction vs speculative claims
- [x] T18: implement bounded verification reads before promotion of concrete claims
- [x] T19: implement downgrade/quarantine paths for unverifiable concrete claims
- [x] T20: add claim-verification artifacts to audit output
- [x] T21: add tests for counts, path names, framework choices, and project-identity claims

## WS5 — Grep-first transcript probing
- [x] T22: implement orient-stage anchor generation for transcript probes
- [x] T23: implement grep/probe-first transcript scanning
- [x] T24: implement bounded-window reads around hits
- [x] T25: implement escalation policy only when confidence remains low or contradiction risk remains high
- [x] T26: record transcript-probe reports
- [x] T27: add tests proving no bulk transcript load in default runs
- [ ] T28 [P]: tune probe budgets and ambiguity thresholds against seeded corpora

## WS6 — Index discipline and generated-only views
- [x] T29: enforce topic/state update before index regeneration
- [x] T30: make `MEMORY.md`, `project.md`, and `user.md` generated-only from canonical state
- [x] T31: tighten pointer-line budgets and require stable record/topic identifiers in startup index entries
- [x] T32: add drift detection between canonical state and generated markdown views
- [x] T33: add tests for manual drift, regeneration, and index budget enforcement

## WS7 — Contradiction graph and retrieval
- [x] T34: implement relation-edge storage and helpers
- [x] T35: backfill relation edges from existing contradiction/supersession metadata where possible
- [x] T36: add relation-aware retrieval boosts/penalties
- [x] T37: add explicit contradiction/supersession explanations to retrieval responses
- [x] T38: add review/query helpers for relation clusters
- [x] T39: add tests for relation-aware ranking and conflict surfacing

## WS8 — Reconciliation sweeps
- [x] T40: implement reconciliation sweep command / runtime entrypoint
- [x] T41: detect renamed roots, orphan views, stale topic files, dead references, and memory-root drift
- [x] T42: implement bounded repair actions and provenance-safe outcomes
- [x] T43: emit reconciliation reports
- [x] T44: add tests for rename/orphan/staleness cases
- [ ] T45 [P]: add periodic reconciliation integration into maintenance/tick where appropriate

## WS9 — Procedural memory elevation
- [x] T46: extend procedural memory representation with preconditions, recovery steps, anti-patterns, and success markers
- [x] T47: improve extractor/parser for workflow structure
- [x] T48: add procedural-aware retrieval prioritization for task-shaped queries
- [x] T49: add eval fixtures for procedural reuse and recovery
- [x] T50: add tests for richer workflow extraction and reuse

## WS10 — Review UX and observability
- [x] T51: extend observability API/read models for verification provenance, relation clusters, probe traces, and reconciliation
- [x] T52: extend webapp/review surfaces with contradiction graphs and generated-view health
- [x] T53: add memory-hurt / stale-claim diagnostic panels
- [x] T54: add deep-linkable detail views for verification and reconciliation artifacts
- [x] T55: add tests for new observability surfaces

## WS11 — Evals, scorecard, and release gates
- [x] T56: define memory-excellence scorecard and thresholds
- [x] T57: implement stale-claim seeded eval corpus
- [x] T58: implement contradiction-resolution eval corpus/metric
- [x] T59: implement derivability-hygiene checks
- [x] T60: integrate repeated coding-task outcome eval into scorecard
- [x] T61: integrate concurrency safety and generated-view integrity into scorecard
- [x] T62: archive scorecard in `make release-check`
- [x] T63: fail `make verify` / release-check on threshold regressions
- [ ] T64: add docs/benchmarks methodology updates

## WS12 — Docs and release positioning
- [ ] T65: update README memory sections to reflect verified/bounded/relation-aware runtime
- [ ] T66: update FAQ with generated-view discipline, verified writes, and reconciliation behavior
- [ ] T67: update benchmark/comparison docs with the new scorecard and limitations
- [ ] T68: update review/observability docs if present
- [ ] T69: add wording checks so docs cannot drift back toward misleading claims
- [ ] T70: run full manual release matrix and reconcile all acceptance criteria

## Parallelizable
- [x] [P] TP1: schemas + docs scaffolding can proceed in parallel with runtime work
- [x] [P] TP2: relation-edge work can proceed in parallel with reconciliation once schemas land
- [x] [P] TP3: observability surfaces can proceed in parallel after report contracts stabilize
- [x] [P] TP4: eval harness work can proceed in parallel after scorecard schema lands

## Required verification commands
- [x] V1: targeted unit tests for claim verification, transcript probes, relation edges, and reconciliation
- [x] V2: targeted integration tests for boundary enforcement, generated views, and retrieval ranking
- [x] V3: `./.venv/bin/python -m ruff check opendream tests scripts`
- [x] V4: `./.venv/bin/python -m mypy opendream scripts`
- [x] V5: `make verify`
- [ ] V6: `make release-check`
- [ ] V7: manual validation of repeated coding-task improvement and observability surfaces

## Completion checklist
- [x] runtime boundaries enforced
- [x] verified writes implemented
- [x] grep-first probing default
- [x] generated-only views enforced
- [x] contradiction graph central to retrieval/review
- [x] reconciliation sweeps implemented
- [x] procedural memory strengthened
- [x] observability/review surfaces updated
- [x] scorecard and release gates passing
- [ ] no further memory-excellence engineering is required before release
