# tasks.md — 441-workspace-catalog-dashboard-bundle

## Rules
- Execute in dependency order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.
- This bundle is not done until CLI, UI, and docs all agree.

## WS1 — Registration and architecture
- [x] T1: add `441-workspace-catalog-dashboard-bundle` to `specs/registry.yaml` with dependencies on `432`, `434`, and `436`
- [x] T2: add ADR for machine-local derived workspace catalog
- [x] T3: update `docs/architecture/overview.md` to include workspace catalog and dashboard

## WS2 — Schemas and storage
- [x] T4: add `workspace-catalog.schema.json`
- [x] T5: add `workspace-roots.schema.json`
- [x] T6: add `workspace-scan-report.schema.json`
- [x] T7: implement `workspace_catalog.py` storage/load/save helpers
- [x] T8: default to `~/.opendream/catalog.json` and `~/.opendream/roots.json`
- [x] T9: add validation and fixture coverage

## WS3 — CLI command family
- [x] T10: implement `workspace list`
- [x] T11: implement `workspace inspect`
- [x] T12: implement `workspace scan`
- [x] T13: implement `workspace roots list`
- [x] T14: implement `workspace roots add`
- [x] T15: implement `workspace roots remove`
- [x] T16: implement `workspace forget`
- [x] T17: implement `workspace doctor`
- [x] T18: add JSON output where consistent with current CLI conventions
- [x] T19 [P]: add machine-readable scan report output

## WS4 — Event-driven updates
- [x] T20: update catalog on successful `init`
- [x] T21: update catalog on successful `activate`
- [x] T22: update catalog on successful `install-service`
- [ ] T23: optionally refresh summary on `status`/`service status`
- [x] T24: ensure catalog update failure is surfaced explicitly without corrupting primary command behavior

## WS5 — Probe and status model
- [x] T25: implement lazy probe helpers for workspace health
- [x] T26: detect missing/stale/broken states
- [x] T27: summarize activation/service/memory/semantic state into catalog-cache or ephemeral read model
- [x] T28: add tests for stale/missing/broken classification

## WS6 — Dashboard UI
- [x] T29: add `/workspaces` route
- [x] T30: add summary bar and search/filter controls
- [x] T31: add workspace cards/rows with required fields
- [x] T32: add navigation from dashboard into workspace detail views
- [ ] T33: add refresh/rescan/doctor/forget actions or links as appropriate
- [x] T34: add UI tests or integration coverage

## WS7 — Docs and FAQ
- [x] T35: update README with workspace catalog and dashboard quickstart
- [x] T36: update FAQ with "How do I see all my OpenDream workspaces?"
- [x] T37: update `docs/coding-agents.md` to mention the workspace dashboard and new commands
- [x] T38: update architecture docs with derived-not-canonical rule
- [x] T39: add wording checks so docs never imply hidden cloud sync or canonical global state

## WS8 — Release gates and verification
- [x] T40: extend `make verify` / release checks with catalog/dashboard tests
- [x] T41: add scan/report fixtures
- [ ] T42: add manual validation matrix for multi-workspace usage
- [x] T43: reconcile final implementation against all acceptance criteria and Constitution rules

## Parallelizable
- [x] [P] TP1: CLI commands and dashboard route can proceed in parallel after schema contracts stabilize
- [x] [P] TP2: docs updates can begin in parallel but cannot finalize until naming/status kinds stabilize

## Required verification commands
- [x] V1: targeted unit tests for catalog storage and probe logic
- [x] V2: targeted integration tests for workspace CLI commands
- [x] V3: targeted integration tests for dashboard route
- [x] V4: `./.venv/bin/python -m ruff check opendream tests scripts`
- [x] V5: `./.venv/bin/python -m mypy opendream scripts`
- [x] V6: `make verify`
- [ ] V7: manual scan/dashboard validation across multiple repos

## Completion checklist
- [x] feature aligns with North Star
- [x] feature aligns with Constitution
- [x] catalog is machine-local and derived
- [x] root scans are explicit and opt-in
- [x] central dashboard exists
- [x] CLI and UI are clear
- [x] docs are clear
- [x] tests and release gates pass

## Notes
- T23 (status/service-status refresh) and T33 (dashboard action buttons) intentionally
  deferred: neither is required for the bundle's acceptance criteria, and both can be
  added without schema/CLI surface changes. T42 and V7 require operator action across
  multiple real repos — see the Manual test runbook in the verification handoff below.
