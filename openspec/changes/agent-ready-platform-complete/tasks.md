# tasks.md — 436-agent-ready-platform-complete

## Rules
- Execute in dependency order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.
- If a task changes a stable contract, update fixtures and docs in the same change.

## Workstreams

### WS1 — Canonical specs and registry
- [x] T1: add `436-agent-ready-platform-complete` to `specs/registry.yaml` with touched surfaces, dependencies, and verification (OpenSpec change dir: `agent-ready-platform-complete/`)
- [x] T2: add any required ADR placeholders for enduring design decisions
- [x] T3: update `docs/architecture/overview.md` to include package generation, contract export, engine registry, guidance-drift, and isolated execution

### WS2 — Path-scoped guidance and canonical routing
- [x] T4: add or update path-scoped guidance files for `opendream/`, `openspec/`, `.meta/spec-adapters/`, and `tests/`
- [x] T5: refactor root `AGENTS.md` to stay concise while explicitly referencing path-scoped guidance
- [x] T6: add tests or conformance checks proving precedence and absence of canonical policy duplication
- [ ] T7 [P]: generate vendor-facing instruction projections from canonical guidance inputs

### WS3 — Stable machine-readable contracts
- [x] T8: add a contract export schema and fixtures directory
- [x] T9: implement `opendream contract export --format json`
- [x] T10: include command inventory, schema inventory, output version map, supported engines, supported package targets, and example payloads
- [x] T11: add snapshot/fixture tests for contract export
- [x] T12: update docs with contract-consumer guidance

### WS4 — MCP inventory and conformance
- [x] T13: replace the placeholder `docs/mcp/servers.md` with a fully populated canonical inventory
- [ ] T14: add an optional machine-readable MCP export or parser for conformance checks
- [ ] T15: add adapter/package validation that rejects undeclared MCP references
- [x] T16: add docs covering auth model, revocation path, and approval boundary requirements
- [ ] T17 [P]: add MCP inventory tests and negative cases

### WS5 — Package generation and validation
- [ ] T18: define package metadata model for supported vendor targets
- [ ] T19: implement `opendream package scaffold/build/validate/manifest`
- [ ] T20: implement Codex package generation with required manifest layout
- [ ] T21: implement Claude Code package generation with plugin + marketplace metadata
- [ ] T22: implement Cursor package generation with rules/skills/hooks packaging
- [ ] T23: implement GitHub Copilot instruction-pack generation with repository-wide and path-scoped outputs
- [ ] T24: emit package build reports with source hash and generated file list
- [ ] T25: add smoke tests in temp repos for all targets
- [ ] T26 [P]: add docs and README quickstarts for all targets

### WS6 — Engine registry and built-in engines
- [ ] T27: add engine registry schema(s) and storage layout
- [ ] T28: implement `opendream engine list/inspect/validate/install/disable`
- [ ] T29: migrate current `435` built-ins to registry-backed built-in engine ids
- [ ] T30: extend automation job registration to resolve through the engine registry
- [ ] T31: reject unknown engine ids and undeclared unattended shell paths
- [ ] T32: add engine manifest tests, registry tests, and migration tests
- [ ] T33 [P]: add contract export coverage for engine registry contents

### WS7 — Guidance-drift automations
- [ ] T34: define guidance-drift record/report schema extensions if needed
- [ ] T35: implement friction signal extraction from task outcomes, corrections, verification failures, and repeated loops
- [ ] T36: implement clustering and scoring for repeated friction
- [ ] T37: implement proposal record emission with evidence refs, target surface, risk, and confidence
- [ ] T38: implement promotion/rejection flows that keep default behavior proposal-only
- [ ] T39: add at least one built-in engine for guidance-drift and one for repo-maintenance reflection
- [ ] T40: add tests for deterministic clustering, proposal-only lifecycle, and promotion provenance
- [ ] T41 [P]: surface accepted proposals in status/context without obscuring core memory

### WS8 — Isolated execution for code-mutating automation
- [ ] T42: add worktree policy fields to automation job / run metadata
- [ ] T43: implement worktree manager helpers and CLI
- [ ] T44: implement `opendream automation run --isolated` and automatic isolated execution for `code_mutation` engines
- [ ] T45: block unattended primary-workspace mutation by policy and tests
- [ ] T46: emit diff summary, base ref, cleanup result, and preserved debug paths in run reports
- [ ] T47: add at least one safe code-mutation built-in example or test-only fixture engine
- [ ] T48: add end-to-end temp-repo tests for isolated code-mutation runs
- [ ] T49 [P]: add operator docs for worktree lifecycle and cleanup

### WS9 — Release gates, docs, and migration
- [ ] T50: extend `make verify` and repo verification scripts with all new conformance checks
- [ ] T51: add release-gate evaluator(s) for package generation, contracts, MCP inventory, engine registry, guidance-drift, and isolated execution
- [ ] T52: update `README.md`, `docs/coding-agents.md`, and architecture docs
- [ ] T53: add migration docs for current adapter users and current `435` automation users
- [ ] T54: run and document the full manual validation matrix
- [ ] T55: reconcile final implementation against all acceptance criteria and constitution rules

## Parallelizable
- [ ] [P] TP1: package target generators can be developed in parallel once metadata contracts stabilize
- [ ] [P] TP2: path-scoped guidance and MCP inventory docs can proceed in parallel with schema work
- [ ] [P] TP3: guidance-drift engines can proceed in parallel after registry contracts land
- [ ] [P] TP4: isolated execution test harnesses can proceed in parallel with worktree manager plumbing

## Required verification commands
- [ ] V1: run targeted unit tests for registry, contracts, package generation, guidance scoring, and worktree policies
- [ ] V2: run targeted integration tests for package smoke validation and automation engine execution
- [x] V3: run `./.venv/bin/python -m ruff check opendream tests scripts`
- [x] V4: run `./.venv/bin/python -m mypy opendream scripts`
- [x] V5: run `make verify`
- [ ] V6: manually validate one generated package per target in a temp repo or temp workspace
- [ ] V7: manually validate one isolated code-mutation automation flow in a temp repo

## Completion checklist
- [ ] all acceptance criteria satisfied
- [ ] no constitution violations
- [ ] generated package outputs remain thin and non-normative
- [x] contract export and fixtures synchronized
- [ ] undeclared MCP references rejected
- [ ] no arbitrary unattended shell execution path
- [ ] unattended code mutation requires isolated worktree mode
- [x] tests and release gates pass (for landed slice; full program pending)
