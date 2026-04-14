# memory-explorer-query-surface

## Why

The observability webapp Memory Explorer needed parity with the `/api/memories` contract: salience/confidence ranges, created/updated time windows, explicit sort direction, stable numeric sorting, pagination limits, and a UI that keeps URL state shareable at scale.

## Goal

Document and ship the query surface implied by `415-memory-observability-api-surface` AC-2 so operators can scan thousands of durable memories without unbounded client renders.

## What changed

- `query_memories` in `opendream/observability.py`: range and time filters, `sort_dir`, correct numeric/datetime ordering, stable `memory_id` tie-break.
- `GET /api/memories` in `opendream/webapp.py`: parses new query parameters; clamps `limit` to 500.
- Memory Explorer UI in `INDEX_HTML`: toolbar, advanced filters, sort controls, pagination, sticky table header, result counts.
- Tests: `tests/test_query_memories.py` and integration coverage in `tests/test_observability.py`.
- Canonical documentation: `specs/415-memory-observability-api-surface/spec.md` (this change set).

## Success criteria

- `/api/memories` honors documented query parameters with deterministic ordering.
- Explorer uses server-side pagination only (bounded `limit`).
- Unit tests cover filters, ranges, time bounds, sort stability, and pagination.
