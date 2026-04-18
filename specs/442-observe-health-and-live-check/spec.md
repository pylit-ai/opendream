# spec.md — 442-observe-health-and-live-check

## Title
Add an explicit observability health contract and live end-to-end check

## Why
The current observability UI can look "ready" while leaving operators unsure what that state actually proves. OpenDream needs a narrow health contract that separates startup, readiness, and liveness, plus a one-click live check that proves the observe server can append a fresh event and surface it back through the index.

## In scope
- `GET /api/health` as a read-only health contract for observe serve
- startup, readiness, and liveness states with explicit reasons and freshness fields
- `POST /api/health/live-check` that performs an end-to-end synthetic probe without creating durable memory
- overview UI updates that show health evidence and let operators run the live check
- regression tests for the health API, live check, and UI contract markers

## Out of scope
- multi-user auth or remote health orchestration
- background alert routing
- synthetic probes that mutate durable memory records
- non-observe CLI status redesign

## User-visible behavior
- Operators can read a single health payload that explains whether observe serve has started, whether the workspace is ready to accept capture, and whether recent signal is flowing.
- Operators can run a live check from the UI or API and receive a concrete probe result with timestamps and freshness evidence.
- Synthetic health probes remain visible as capture evidence but do not become durable memories.

## Acceptance criteria
- [x] AC-1: `GET /api/health` returns `startup`, `readiness`, and `liveness` sections with `status`, `checked_at`, and explicit `reasons`
- [x] AC-2: health payload includes freshness evidence for `index_generated_at`, `last_event_at`, `last_run_at`, and pending queue state
- [x] AC-3: `POST /api/health/live-check` appends a schema-valid probe event, refreshes the observability index, and returns the observed probe metadata
- [x] AC-4: live-check probe events are excluded from durable-memory extraction
- [x] AC-5: overview UI exposes the health evidence and a live-check action without hiding raw API access

## Edge cases
- uninitialized workspaces
- locked stores
- pending events with no consolidation yet
- stale service heartbeat with otherwise readable artifacts
- repeated live checks in the same session

## Required verifiers
- unit tests: yes, health payload construction and probe classification behavior
- integration tests: yes, `/api/health`, `/api/health/live-check`, and observe-serve refresh behavior
- evals / scenario checks: no
- manual verification: yes, serve a real workspace, run live check, and confirm freshness updates in overview

## Risks
- health contract overstates what it proves
- probe events leak into durable memory and create noise
- UI adds a green indicator without enough evidence text

## Links
- `../415-memory-observability-api-surface/spec.md`
- `../416-memory-observability-webapp-mvp/spec.md`
