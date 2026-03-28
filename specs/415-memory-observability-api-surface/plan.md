# plan.md — 415-memory-observability-api-surface

## Summary
Add a thin observability API backed by the read model. Prefer explicit typed responses, auditability for review writes, and narrow, stable endpoints over a generic file browser.

## Architecture impact
- touched components:
  - new API server or route-handler module
  - observability read-model query layer
  - annotation and review-action persistence
  - tests and API fixtures
- unchanged components:
  - canonical memory store layout
  - consolidator mutation logic

## Data model / contract changes
- define endpoint contracts for:
  - `GET /api/overview`
  - `GET /api/memories`
  - `GET /api/memories/:id`
  - `GET /api/memories/:id/lineage`
  - `GET /api/sessions`
  - `GET /api/sessions/:id/timeline`
  - `GET /api/runs`
  - `GET /api/runs/:id`
  - `GET /api/runs/:id/diff`
  - `GET /api/retrievals`
  - `GET /api/retrievals/:id`
  - `GET /api/context/:id`
  - `GET /api/graph`
  - `GET /api/reviews`
  - `GET /api/evals`
  - `GET /api/exports`
  - `POST /api/reviews/:id/{approve,suppress,merge,split}`
  - `POST /api/annotations`
  - `POST /api/exports`

## API rules
- reads must operate on the read model and source artifacts, not ad hoc file scraping per request
- source-of-truth files remain canonical
- write actions must create audit records with actor and timestamp
- APIs must not claim data is complete when artifacts are missing

## Realtime rules
- stream active run status
- stream lock acquisition and release changes
- stream review-queue updates when available

## Rollout
1. add spec and registry entry
2. implement query layer and contracts
3. implement read endpoints
4. implement annotation and review writes
5. add real-time status updates
6. rerun verification

## Rollback
1. remove the API layer
2. keep read model and source artifacts intact

## Verification plan
- run: `make test`
- manual checks:
  - fetch overview, memory detail, run detail, retrieval detail, and session timeline
  - create an annotation and confirm the audit record
  - observe an active run over SSE or websocket

## ADR needed?
- no
