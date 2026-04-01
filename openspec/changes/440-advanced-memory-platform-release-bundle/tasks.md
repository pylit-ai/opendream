# tasks.md — 440-memory-platform-superiority-release-bundle

## Rules
- Execute in dependency order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.
- This bundle is not done until status surfaces, docs, release notes, and the runtime-superiority report all agree.

## WS1 — Registration and architecture
- [ ] T1: add `440-memory-platform-superiority-release-bundle` to `specs/registry.yaml` with explicit dependencies on `404`, `430`, `432`, `433`, `434`, `435`, and `439`
- [ ] T2: add ADR(s) for execution-ownership matrix, delegated ingest, and Codex trust boundary if enduring decisions stabilize
- [ ] T3: update `docs/architecture/overview.md` to describe OpenDream as a memory control plane with multiple execution surfaces

## WS2 — Schemas and contract surfaces
- [ ] T4: add `semantic-execution-policy.schema.json`
- [ ] T5: add `semantic-adapter-manifest.schema.json`
- [ ] T6: add `semantic-setup-report.schema.json`
- [ ] T7: add `delegated-semantic-envelope.schema.json`
- [ ] T8: add `runtime-superiority-report.schema.json`
- [ ] T9: extend semantic config/status models with requested preference, active strategy, candidate strategies, active adapter id, and fallback policy
- [ ] T10: extend contract export with adapter inventory, execution ownership, and auth/source fields
- [ ] T11: add schema fixtures and validation coverage

## WS3 — Setup wizard and detection
- [ ] T12: implement `opendream semantic setup --workspace ...`
- [ ] T13: implement detection for Codex / Claude / Cursor / Gemini / direct-provider config
- [ ] T14: implement ranking logic for `--prefer no-extra-key`
- [ ] T15: implement ranking logic for `--prefer direct-provider`
- [ ] T16: emit machine-readable setup reports and remediation hints
- [ ] T17 [P]: add setup-matrix fixture tests

## WS4 — Codex account executor
- [ ] T18: implement adapter manifest and status logic for `codex-account`
- [ ] T19: add trusted-local/private environment checks
- [ ] T20: scaffold Codex wrapper/config/docs under `.meta/spec-adapters/codex/`
- [ ] T21: add structured-output semantic invocation contract for Codex-backed runs
- [ ] T22: add setup/status negative cases for missing auth cache or unsupported environment
- [ ] T23: add smoke tests and trust-boundary tests

## WS5 — Claude scheduled executor
- [ ] T24: implement adapter manifest and status logic for `claude-scheduled-task`
- [ ] T25: scaffold Desktop-task-compatible semantic refresh assets
- [ ] T26: scaffold Cloud-task-compatible semantic refresh assets
- [ ] T27: scaffold feature-radar / bug-radar / fix-radar / semantic-refresh delegated examples
- [ ] T28: define and validate Claude delegated envelope return contract
- [ ] T29: add tests for scaffold generation, path layout, and wording correctness

## WS6 — Cursor automation executor
- [ ] T30: create `.meta/spec-adapters/cursor/` with README, prompt/instruction assets, and return-path conventions
- [ ] T31: implement adapter manifest and status logic for `cursor-automation`
- [ ] T32: scaffold account-backed automation path and artifact-in-repo return path
- [ ] T33: document programmatic API-key mode separately without making it the default recommendation
- [ ] T34: define and validate Cursor delegated envelope contract
- [ ] T35: add scaffold smoke tests and path tests

## WS7 — Delegated ingest
- [ ] T36: implement `opendream semantic ingest --workspace ...`
- [ ] T37: add inbox scan support and invalid-envelope archival
- [ ] T38: convert accepted envelopes into learned-context proposals and/or event emissions with provenance
- [ ] T39: ensure no direct bypass of verified writes / promotion policy
- [ ] T40: add tests for valid/invalid envelopes and bounded mutation

## WS8 — Feature mining and radar integration
- [ ] T41: add `automation scaffold-dream` or equivalent generator for feature-radar / bug-radar / fix-radar / semantic-refresh
- [ ] T42: integrate delegated Layer C patterns into the canonical dream-task playbook
- [ ] T43: update example assets for feature mining so direct-provider and delegated paths are both runnable
- [ ] T44: add tests for generated job specs / inbox conventions / delegated refresh examples

## WS9 — Status, observability, and review surfaces
- [ ] T45: extend `semantic status`
- [ ] T46: extend `dream status`
- [ ] T47: extend observability/read models with active owner, delegated envelope state, and remediation hints
- [ ] T48: ensure the same review/excellence surfaces remain visible for delegated execution
- [ ] T49: add tests for status/read-model synchronization

## WS10 — Docs, FAQ, benchmark docs, release notes
- [ ] T50: update README semantic section into an execution/auth matrix
- [ ] T51: update FAQ to answer “Do I need extra API keys?” precisely
- [ ] T52: update `docs/coding-agents.md` with direct-provider vs delegated quickstarts
- [ ] T53: update `docs/automation/dream-task-playbook.md` with delegated Layer C variants
- [ ] T54: update `docs/automation/examples/feature-mining.md`
- [ ] T55: update benchmark docs so release claims rely on official docs + OpenDream evidence, not unofficial implementation claims
- [ ] T56: update `CHANGELOG.md` / release-note surfaces
- [ ] T57: add wording checks for unsupported magic claims

## WS11 — Unsupported-path guardrails
- [ ] T58: encode Gemini negative recommendation behavior in setup logic and docs
- [ ] T59: ensure unsupported paths appear in blocked-strategy reports
- [ ] T60: add tests for negative recommendation behavior and wording

## WS12 — Runtime-superiority proof and release gates
- [ ] T61: define `runtime-superiority-report` structure and thresholds
- [ ] T62: integrate memory-excellence scorecard results into the runtime-superiority report
- [ ] T63: add repeated coding-task / delegated-ingest / radar correctness evidence by execution mode
- [ ] T64: add release-check generation and archival of runtime-superiority reports
- [ ] T65: fail release-check on threshold regressions or docs/runtime mismatch
- [ ] T66: run full manual release matrix and reconcile all acceptance criteria

## Parallelizable
- [ ] [P] TP1: Codex / Claude / Cursor scaffolds can proceed in parallel after schema contracts stabilize
- [ ] [P] TP2: docs rewrites can begin in parallel but cannot finalize until status behavior lands
- [ ] [P] TP3: runtime-superiority report work can begin once scorecard and setup schemas stabilize

## Required verification commands
- [ ] V1: targeted unit tests for execution policy, setup wizard, adapter detection, envelope validation
- [ ] V2: targeted integration tests for Codex / Claude / Cursor scaffolds
- [ ] V3: targeted integration tests for delegated ingest and radar scaffolds
- [ ] V4: `./.venv/bin/python -m ruff check opendream tests scripts`
- [ ] V5: `./.venv/bin/python -m mypy opendream scripts`
- [ ] V6: `make verify`
- [ ] V7: `make release-check`
- [ ] V8: manual validation of at least one supported setup path per execution surface

## Completion checklist
- [ ] memory-excellence bundle remains compatible and enforced
- [ ] setup is unambiguous
- [ ] no-extra-key is preferred when actually supported
- [ ] docs and status surfaces tell the truth
- [ ] delegated semantic ingest is validated and bounded
- [ ] feature-mining/radar playbooks work across supported surfaces
- [ ] runtime-superiority report passes
- [ ] no further release-surface engineering is required before release
