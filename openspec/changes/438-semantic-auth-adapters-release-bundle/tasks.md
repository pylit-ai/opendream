# tasks.md — 438-semantic-auth-adapters-release-bundle

## Rules
- Execute in dependency order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.
- This bundle is not done until docs, setup UX, status surfaces, and release wording all agree.

## WS1 — Registry, ADRs, architecture
- [x] T1: add `438-semantic-auth-adapters-release-bundle` to `specs/registry.yaml` with dependencies on `404`, `436`, and `437`
- [x] T2: add ADR(s) for semantic auth/execution matrix and delegated-ingest policy if enduring decisions stabilize
- [x] T3: update `docs/architecture/overview.md` to include direct-provider vs delegated semantic execution

## WS2 — Schemas and execution policy
- [x] T4: add `semantic-adapter-manifest.schema.json`
- [x] T5: add `semantic-adapter-status.schema.json`
- [x] T6: add `semantic-setup-report.schema.json`
- [x] T7: add `delegated-semantic-envelope.schema.json`
- [x] T8: add `semantic-execution-policy.schema.json`
- [x] T9: extend semantic config/status models with active strategy, preferred auth mode, candidate strategies, and fallback policy
- [x] T10: add validation and contract-export coverage for the new fields

## WS3 — Setup wizard and detection
- [x] T11: implement `opendream semantic setup --workspace ...`
- [x] T12: implement adapter detection for Codex / Claude / Cursor / Gemini
- [x] T13: implement recommendation policy for `--prefer no-extra-key`
- [x] T14: implement recommendation policy for `--prefer direct-provider`
- [x] T15: write machine-readable setup report output
- [x] T16: add negative recommendations and remediation hints
- [x] T17 [P]: add setup fixture tests across multiple tool-detection combinations

## WS4 — Codex account-auth semantic adapter
- [x] T18: implement semantic adapter manifest and runner for `codex-account`
- [x] T19: add trusted-environment checks and warnings
- [x] T20: scaffold Codex-specific wrapper/config docs under `.meta/spec-adapters/codex/`
- [x] T21: add structured-output invocation contract for Codex semantic runs
- [x] T22: add status/health reporting for Codex adapter
- [x] T23: add tests for no-auth / missing-binary / trusted-private vs unsupported-public recommendations
- [x] T24 [P]: add smoke fixtures for local trusted-runner and advanced persistent-auth patterns

## WS5 — Claude scheduled-task semantic adapter
- [x] T25: implement adapter manifest for `claude-scheduled-task`
- [x] T26: scaffold repo-local command/skill/prompt for semantic refresh under Claude
- [x] T27: scaffold Desktop-task guidance/output path
- [x] T28: scaffold Cloud-task guidance/output path
- [x] T29: add optional GitHub Actions-compatible delegated path docs
- [x] T30: define Claude delegated envelope return contract
- [x] T31: add status/health reporting for Claude adapter
- [x] T32: add tests for scaffold generation and wording correctness

## WS6 — Cursor automation semantic adapter
- [x] T33: implement adapter manifest for `cursor-automation`
- [x] T34: scaffold automation prompt/instructions and artifact-in-repo return path
- [x] T35: define `.opendream/inbox/semantic/cursor/` conventions
- [x] T36: document account-backed UI path vs API-key programmatic path
- [x] T37: add status/health reporting for Cursor adapter
- [x] T38: add scaffold smoke tests and artifact-path tests

## WS7 — Delegated envelope ingest
- [x] T39: implement `opendream semantic ingest --workspace ...`
- [x] T40: add inbox scan support and archive/failure handling
- [x] T41: convert accepted envelopes into learned-context proposals and/or event emissions
- [x] T42: add provenance linking back to delegated adapter and run metadata
- [x] T43: add tests for valid/invalid envelopes and bounded mutation semantics

## WS8 — Status, observability, and contract export
- [x] T44: extend `opendream semantic status`
- [x] T45: extend `opendream dream status`
- [x] T46: extend contract export with adapter inventory and auth matrix
- [x] T47: extend observability/UI surfaces with semantic execution owner and delegated envelope state
- [x] T48: add tests for status surface and contract export synchronization

## WS9 — Docs, FAQ, playbooks, and release notes
- [x] T49: update `README.md` semantic section with explicit auth/execution matrix
- [x] T50: update `docs/FAQ.md` to answer "do I need extra API keys?" precisely
- [x] T51: update `docs/coding-agents.md` with setup quickstarts and adapter matrix
- [x] T52: update `docs/automation/dream-task-playbook.md` to separate local direct-provider Layer C from delegated Layer C
- [x] T53: update benchmark/comparison docs so claims match actual supported execution modes
- [x] T54: update `CHANGELOG.md` / release-note surfaces
- [x] T55 [P]: add dedicated adapter/setup docs under canonical existing doc homes, not ad hoc categories

## WS10 — Security and unsupported-path policy
- [x] T56: encode Gemini negative recommendation behavior in setup logic and docs
- [x] T57: add secret-redaction rules for Codex auth-cache references
- [x] T58: ensure public/untrusted CI contexts never default to Codex account-backed mode
- [x] T59: add policy tests and wording tests for unsupported paths

## WS11 — Release gates and verification
- [x] T60: extend `make verify` and/or release-check with docs honesty gate
- [x] T61: add release wording checks for unsupported magic claims
- [x] T62: add adapter scaffold smoke stage(s) to verification
- [x] T63: add setup-wizard matrix tests to verification
- [x] T64: run full manual validation matrix and document results
- [x] T65: reconcile final implementation against all acceptance criteria and constitution rules

## Parallelizable
- [x] [P] TP1: Codex / Claude / Cursor scaffold generation can proceed in parallel after schemas and setup report stabilize
- [x] [P] TP2: docs rewrite can begin in parallel with adapter work, but cannot be finalized until status behavior is fixed
- [x] [P] TP3: observability/read-model updates can proceed in parallel with delegated ingest once schema contracts land

## Required verification commands
- [x] V1: targeted unit tests for execution policy, setup wizard, adapter detection, and validation
- [x] V2: targeted integration tests for Codex/Claude/Cursor scaffolds
- [x] V3: targeted integration tests for delegated envelope ingest
- [x] V4: `./.venv/bin/python -m ruff check opendream tests scripts`
- [x] V5: `./.venv/bin/python -m mypy opendream scripts`
- [x] V6: `make verify`
- [x] V7: release-check / wording-gate verification
- [x] V8: manual validation of at least one setup path per supported no-extra-key adapter

## Completion checklist
- [x] setup is unambiguous
- [x] release notes no longer imply magic
- [x] no-extra-key is the default path when supported
- [x] unsupported OAuth reuse is never recommended
- [x] direct-provider mode still works
- [x] delegated ingest is validated and auditable
- [x] status/UI/docs all agree on the active semantic execution model
- [x] tests and release gates pass
