# tasks.md — 440-advanced-memory-platform-release-bundle

## Rules
- Execute in dependency order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.
- This bundle is not done until status surfaces, docs, release notes, and the advanced-runtime report all agree.

## WS1 — Registration and architecture
- [x] T1: add `440-advanced-memory-platform-release-bundle` to `specs/registry.yaml` with explicit dependencies on `404`, `430`, `432`, `433`, `434`, `435`, and `439`
- [x] T2: add ADR(s) for execution-ownership matrix, delegated ingest, and Codex trust boundary if enduring decisions stabilize
- [x] T3: update `docs/architecture/overview.md` to describe OpenDream as a memory control plane with multiple execution surfaces

## WS2 — Schemas and contract surfaces
- [x] T4: add `semantic-execution-policy.schema.json`
- [x] T5: add `semantic-adapter-manifest.schema.json`
- [x] T6: add `semantic-setup-report.schema.json`
- [x] T7: add `delegated-semantic-envelope.schema.json`
- [x] T8: add `advanced-runtime-report.schema.json`
- [x] T9: extend semantic config/status models with requested preference, active strategy, candidate strategies, active adapter id, and fallback policy
- [x] T10: extend contract export with adapter inventory, execution ownership, and auth/source fields
- [x] T11: add schema fixtures and validation coverage

## WS3 — Setup wizard and detection
- [x] T12: implement `opendream semantic setup --workspace ...`
- [x] T13: implement detection for Codex / Claude / Cursor / Gemini / direct-provider config
- [x] T14: implement ranking logic for `--prefer no-extra-key`
- [x] T15: implement ranking logic for `--prefer direct-provider`
- [x] T16: emit machine-readable setup reports and remediation hints
- [x] T17 [P]: add setup-matrix fixture tests

## WS4 — Codex account executor
- [x] T18: implement adapter manifest and status logic for `codex-account`
- [x] T19: add trusted-local/private environment checks
- [x] T20: scaffold Codex wrapper/config/docs under `.meta/spec-adapters/codex/`
- [x] T21: add structured-output semantic invocation contract for Codex-backed runs
- [x] T22: add setup/status negative cases for missing auth cache or unsupported environment
- [x] T23: add smoke tests and trust-boundary tests

## WS5 — Claude scheduled executor
- [x] T24: implement adapter manifest and status logic for `claude-scheduled-task`
- [x] T25: scaffold Desktop-task-compatible semantic refresh assets
- [x] T26: scaffold Cloud-task-compatible semantic refresh assets
- [x] T27: scaffold feature-radar / bug-radar / fix-radar / semantic-refresh delegated examples
- [x] T28: define and validate Claude delegated envelope return contract
- [x] T29: add tests for scaffold generation, path layout, and wording correctness

## WS6 — Cursor automation executor
- [x] T30: create `.meta/spec-adapters/cursor/` with README, prompt/instruction assets, and return-path conventions
- [x] T31: implement adapter manifest and status logic for `cursor-automation`
- [x] T32: scaffold account-backed automation path and artifact-in-repo return path
- [x] T33: document programmatic API-key mode separately without making it the default recommendation
- [x] T34: define and validate Cursor delegated envelope contract
- [x] T35: add scaffold smoke tests and path tests

## WS7 — Delegated ingest
- [x] T36: implement `opendream semantic ingest --workspace ...`
- [x] T37: add inbox scan support and invalid-envelope archival
- [x] T38: convert accepted envelopes into learned-context proposals and/or event emissions with provenance
- [x] T39: ensure no direct bypass of verified writes / promotion policy
- [x] T40: add tests for valid/invalid envelopes and bounded mutation

## WS8 — Feature mining and radar integration
- [x] T41: add `automation scaffold-dream` or equivalent generator for feature-radar / bug-radar / fix-radar / semantic-refresh
- [x] T42: integrate delegated Layer C patterns into the canonical dream-task playbook
- [x] T43: update example assets for feature mining so direct-provider and delegated paths are both runnable
- [x] T44: add tests for generated job specs / inbox conventions / delegated refresh examples

## WS9 — Status, observability, and review surfaces
- [x] T45: extend `semantic status`
- [x] T46: extend `dream status`
- [x] T47: extend observability/read models with active owner, delegated envelope state, and remediation hints
- [x] T48: ensure the same review/excellence surfaces remain visible for delegated execution
- [x] T49: add tests for status/read-model synchronization

## WS10 — Docs, FAQ, benchmark docs, release notes
- [x] T50: update README semantic section into an execution/auth matrix
- [x] T51: update FAQ to answer “Do I need extra API keys?” precisely
- [x] T52: update `docs/coding-agents.md` with direct-provider vs delegated quickstarts
- [x] T53: update `docs/automation/dream-task-playbook.md` with delegated Layer C variants
- [x] T54: update `docs/automation/examples/feature-mining.md`
- [x] T55: update benchmark docs so release claims rely on official docs + OpenDream evidence, not unofficial implementation claims
- [x] T56: update `CHANGELOG.md` / release-note surfaces
- [x] T57: add wording checks for unsupported magic claims

## WS11 — Unsupported-path guardrails
- [x] T58: encode Gemini negative recommendation behavior in setup logic and docs
- [x] T59: ensure unsupported paths appear in blocked-strategy reports
- [x] T60: add tests for negative recommendation behavior and wording

## WS12 — Advanced runtime proof and release gates
- [x] T61: define `advanced-runtime-report` structure and thresholds
- [x] T62: integrate memory-excellence scorecard results into the advanced-runtime report
- [x] T63: add repeated coding-task / delegated-ingest / radar correctness evidence by execution mode
- [x] T64: add release-check generation and archival of advanced-runtime reports
- [x] T65: fail release-check on threshold regressions or docs/runtime mismatch
- [x] T66: run full manual release matrix and reconcile all acceptance criteria

## Parallelizable
- [x] [P] TP1: Codex / Claude / Cursor scaffolds can proceed in parallel after schema contracts stabilize
- [x] [P] TP2: docs rewrites can begin in parallel but cannot finalize until status behavior lands
- [x] [P] TP3: advanced-runtime report work can begin once scorecard and setup schemas stabilize

## Required verification commands
- [x] V1: targeted unit tests for execution policy, setup wizard, adapter detection, envelope validation
- [x] V2: targeted integration tests for Codex / Claude / Cursor scaffolds
- [x] V3: targeted integration tests for delegated ingest and radar scaffolds
- [x] V4: `./.venv/bin/python -m ruff check opendream tests scripts`
- [x] V5: `./.venv/bin/python -m mypy opendream scripts`
- [x] V6: `make verify`
- [ ] V7: `make release-check`
- [ ] V8: manual validation of at least one supported setup path per execution surface

## Completion checklist
- [x] memory-excellence bundle remains compatible and enforced
- [x] setup is unambiguous
- [x] no-extra-key is preferred when actually supported
- [x] docs and status surfaces tell the truth
- [x] delegated semantic ingest is validated and bounded
- [x] feature-mining/radar playbooks work across supported surfaces
- [x] advanced-runtime report passes
- [ ] no further release-surface engineering is required before release
