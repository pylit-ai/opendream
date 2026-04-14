# spec.md — 415-memory-observability-api-surface

## Title
Expose read-only observability APIs for memory state, runs, retrievals, sessions, and context

## Why
The read model alone does not make the system inspectable by humans or tools. OpenDream needs a thin API layer that exposes overview, memory, run, retrieval, session, graph, and export surfaces without creating a second source of truth or mutating the memory store during reads.

## In scope
- read APIs for overview, memories, runs, retrievals, sessions, context, reviews, evals, exports, and lineage
- annotation and review-action write APIs with explicit audit logging
- pagination, filtering, sorting, and broken-artifact tolerance
- SSE or websocket updates for active run status, lock state, and review queue changes
- API contracts backed by the observability read model

## Out of scope
- full frontend implementation
- arbitrary file browsing
- graph editing
- replaying or mutating consolidation runs beyond explicit review actions

## User-visible behavior
- Consumers can fetch the current overview, detailed memory records, retrieval traces, context assemblies, and run diffs over stable endpoints.
- Review and annotation writes are explicit, auditable, and actor-attributed.
- APIs expose omitted-memory reasons, score breakdowns, and run-phase diagnostics when the underlying data exists.
- Real-time consumers can observe active runs and lock state without polling raw files.

## Acceptance criteria
- [x] AC-1: read endpoints exist for overview, memories, runs, retrievals, sessions, context, reviews, evals, exports, and lineage
- [x] AC-2: filtering and pagination support memory explorer requirements including type, scope, status, salience, confidence, and time windows
- [x] AC-3: review and annotation writes require actor metadata and emit audit records
- [x] AC-4: API responses preserve provenance and never invent data not present in the read model or source artifacts
- [x] AC-5: real-time updates expose active run status, lock state, and newly completed retrievals

## GET `/api/memories` query parameters

The list endpoint applies filters and sorting server-side, then returns a page slice. Response shape: `{ "total": <int>, "items": [ ... ] }`.

| Parameter | Description |
|-----------|-------------|
| `search` | Case-insensitive substring match across `title`, `summary`, `body`, and `memory_id`. |
| `type`, `scope`, `status` | Exact match when non-empty. |
| `salience_min`, `salience_max` | Inclusive numeric bounds; rows without `salience` are excluded when either bound is set. |
| `confidence_min`, `confidence_max` | Inclusive numeric bounds; rows without `confidence` are excluded when either bound is set. |
| `updated_after`, `updated_before` | Inclusive ISO-8601 bounds on `updated_at`; rows without `updated_at` are excluded when either bound is set. |
| `created_after`, `created_before` | Inclusive ISO-8601 bounds on `created_at`; rows without `created_at` are excluded when either bound is set. |
| `sort` | One of: `title`, `type`, `scope`, `status`, `memory_id`, `created_at`, `updated_at`, `salience`, `confidence`, `retrieval_frequency`. Invalid values fall back to `updated_at`. |
| `sort_dir` | `asc` or `desc`. When omitted, string fields (`title`, `type`, `scope`, `status`, `memory_id`) default ascending; other fields default descending (legacy behavior). |
| `offset` | Non-negative row offset (default `0`, clamped). |
| `limit` | Page size from `1` to `500` (default `50`). |

Sort order is stable: ties break on `memory_id`.

## Edge cases
- page requests against empty stores
- stale read-model snapshots
- malformed review actions
- partial run data where diff or phase details are missing
- clients requesting focused graph neighborhoods around unknown IDs

## Required verifiers
- unit tests: yes, contract serialization and filter parsing
- integration tests: yes, endpoint coverage, pagination, broken-artifact tolerance, and audit writes
- evals / scenario checks: no
- manual verification: yes, exercise core endpoints against a seeded workspace and confirm provenance plus audit output

## Risks
- the API hides gaps in source artifacts instead of surfacing them
- write endpoints mutate canonical memory state without auditable review trails
- real-time surfaces drift from the indexed read model

## Links
- `../414-memory-observability-read-model/spec.md`
- `../../notepads/active/openspec_webapp_autodream_introspection_bundle.md`
