# 437-observability-perf

## Why
The Observe webapp loads can take up to 30 seconds for individual pages. Root cause: every `/api/overview`, `/api/runs`, `/api/retrievals`, `/api/graph` call invokes `load_or_build_index(store)` which scans every memory record, event, retrieval, and run JSON file on disk. With dozens of workspaces in the catalog and large per-workspace event histories, the build cost dominates per-request latency. Users see broken-looking blank pages while waiting and lose trust in the tool.

## Goal
Bring p95 page load to under 1.5s on a steady-state workspace and under 5s on first cold load. Make perceived latency near-zero through stale-while-revalidate rendering. Preserve correctness — no stale data older than the underlying store mutation.

## What changes
- add an in-process index cache in `observability.py` keyed by `(memory_root, mtime fingerprint)`; rebuild only when fingerprint changes
- add cheap fingerprint computation that touches directory mtimes rather than reading file contents
- split list endpoints from detail endpoints: list returns summary projections only; detail endpoints fetch full records
- add `limit` and `since` query params to all list endpoints (`/api/runs`, `/api/retrievals`, `/api/sessions`, `/api/memories` already has limit; ensure consistency)
- add `/api/overview/lite` returning only headline stats for instant first paint; full overview hydrates after
- frontend: prefetch likely next routes on nav-link hover; lower cachedFetch staleness windows where appropriate
- emit per-request timing logs in dev mode; expose a `/api/_perf` endpoint with last-N request timings for diagnosis

## Non-goals
- moving to a database (file-backed store remains canonical)
- adding a long-lived daemon process
- breaking existing API shapes; lite/since are additive

## Success criteria
- p95 `/api/overview` < 250ms on a workspace with 1k memories
- first paint of any route < 500ms when index cache is warm
- no observed staleness > one fingerprint cycle (≤ 1s) under normal mutation
- Workspaces, Memories, Runs pages all render skeletons + first useful content in under 500ms
