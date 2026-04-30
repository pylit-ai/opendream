# Tasks

## P0 — index cache
- [ ] add `IndexCache` keyed by memory_root + fingerprint to `observability.py`
- [ ] implement `_index_fingerprint(store)` using directory mtimes only
- [ ] rewrite `load_or_build_index` to consult cache + rebuild on miss
- [ ] add `force=True` invalidation for tests
- [ ] add LRU eviction (cap 16 roots)
- [ ] env override `OPENDREAM_DISABLE_INDEX_CACHE=1`

## P0 — endpoint shape
- [ ] add `/api/overview/lite` with counts + posture + 5 recent runs only
- [ ] add `limit` + `since` to list endpoints; clamp server-side
- [ ] strip heavy fields from list projections; keep on detail endpoints

## P0 — perf telemetry
- [ ] request-timing middleware → ring buffer
- [ ] expose `/api/_perf` for in-product diagnosis
- [ ] dev-mode slow-request log (> 250ms)

## P0 — frontend integration
- [ ] hover-prefetch on nav items via `cachedFetch`
- [ ] true stale-while-revalidate in `cachedFetch`: return cached immediately + refetch
- [ ] Overview route: render from `/api/overview/lite` first, upgrade to full
- [ ] Dev perf indicator (last fetch ms) in `PerfBanner`

## P0 — verification
- [ ] benchmark harness: p50/p95 for `/api/overview` at 100/1000/10000 memories
- [ ] regression test: cached vs rebuilt index payloads match
- [ ] staleness test: post-mutation freshness < 1s
- [ ] e2e: each route first-paint < 500ms with warm cache

## P1 — docs
- [ ] document `/api/overview/lite` and pagination params
- [ ] document `OPENDREAM_DISABLE_INDEX_CACHE` toggle
- [ ] add troubleshooting section for `/api/_perf`
