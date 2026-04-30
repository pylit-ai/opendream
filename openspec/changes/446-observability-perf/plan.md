# Execution plan

## Phase 1 — index cache
1. Add `IndexCache` in `observability.py` storing `(fingerprint, index)` per memory root.
2. Implement `_index_fingerprint(store)` that returns a tuple of `(memory_root_mtime, events_dir_mtime, runs_dir_mtime, retrievals_dir_mtime, audit_dir_mtime)` via `os.stat` only — no file content reads.
3. Rewrite `load_or_build_index(store)` to consult the cache; rebuild only on fingerprint mismatch.
4. Add a `force=True` argument for tests / explicit invalidation.
5. Add an LRU eviction policy (cap at 16 cached roots) to bound memory growth.

## Phase 2 — endpoint shape
6. Add `/api/overview/lite` returning a small struct (counts, posture, last 5 runs) without scanning the full graph.
7. Add `limit` + `since` to `/api/runs`, `/api/retrievals`, `/api/sessions` where missing; clamp `limit` server-side.
8. Promote list endpoints to return summary projections (drop heavy fields like full retrieval candidates from list view; keep full payload behind detail endpoints).

## Phase 3 — perf telemetry + observability
9. Wrap each handler in a request-timing decorator that records `(path, query_keys, ms)` into a ring buffer.
10. Expose `/api/_perf` returning the last 200 request timings for in-product diagnosis.
11. In dev mode, log slow requests (> 250ms) with stack hints.

## Phase 4 — frontend
12. Prefetch on nav-link hover: AppShell adds `onMouseEnter` to nav items that calls `cachedFetch` for the route's primary endpoint.
13. Switch to true stale-while-revalidate: render last cached value immediately, fire refetch in parallel, swap on success.
14. Render `OverviewRoute` from `/api/overview/lite` for first paint; upgrade to full overview when arrived.
15. Add a tiny perf indicator in dev builds showing last fetch durations.

## Verification
- benchmark harness measuring `/api/overview` p50/p95 with 100, 1000, 10000 memories
- regression test: index cache returns identical payload to direct rebuild for the same fingerprint
- staleness test: after a mutation, fingerprint changes within 1s and the next call sees fresh data
- frontend e2e: navigate to each route in sequence, assert each first-paint < 500ms with warm cache

## Rollback
- index cache can be disabled via env `OPENDREAM_DISABLE_INDEX_CACHE=1`
- `/api/overview/lite` is additive; legacy `/api/overview` continues to work
