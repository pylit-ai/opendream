# tasks.md — 444-managed-runtime-and-memory-surface-overview

## Rules
- Execute in dependency order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## WS1 — Managed runtime policy
- [x] T1: add `444-managed-runtime-and-memory-surface-overview` to `specs/registry.yaml`
- [x] T2: add workspace-local runtime policy plus a shared ensure-runtime service path
- [x] T3: wire primary commands to ensure the background runtime by default with an explicit opt-out

## WS2 — CLI and UI service control
- [x] T4: expose runtime policy and idempotent ensure/start/stop/restart controls in CLI JSON and human surfaces
- [x] T5: expose matching service controls from observe `/settings` via shared API paths

## WS3 — Dream and memory introspection
- [x] T6: add overview summaries for latest dream mutation effects and current memory-surface state
- [x] T7: expose those summaries in `/api/overview` and render digestible panels in `/overview`
- [x] T8: preserve links to detailed raw JSON, runs, diffs, and memory explorer routes

## WS4 — Verification and docs
- [x] T9: add regression tests for managed-runtime default behavior and explicit opt-out
- [x] T10: add API/UI tests for service controls and overview summaries
- [x] T11: update README and operator docs for the new managed-runtime primary path

## WS5 — Semantic runtime materialization
- [x] T12: make the managed worker auto mode consume explicit-event semantic backlog instead of stalling on transcript-only logic
- [x] T13: expose a shared semantic-pipeline diagnosis in `service status`, `/api/overview`, and observe UI panels
- [x] T14: refresh docs and setup/apply flow so operators use semantic setup validation and `dream worker --once --mode auto`, not `semantic bootstrap`, for readiness repair

## Required verification commands
- [x] V1: targeted unit and integration tests for runtime policy, ensure-runtime, and overview summaries
- [x] V2: `./.venv/bin/python -m ruff check opendream tests scripts`
- [x] V3: `./.venv/bin/python -m mypy opendream scripts`
- [x] V4: `make verify`
- [x] V5: `make release-check`
