# plan.md — 444-managed-runtime-and-memory-surface-overview

## Approach
- Add in-page Memories tabs for Surface, Explorer, and Changes.
- Use the existing overview memory-surface and last-runtime-effects read models for `/memories/surface`.
- Keep the existing memory explorer implementation, moving it to `/memories/explorer` while preserving `/memories/<id>` compatibility.
- Move semantic comparison UX to `/memories/changes` while preserving `/semantic-changes`.

## Files
- `opendream/webapp.py` owns the sidebar shell link.
- `opendream/static/observe-ui.js` owns SPA routes and rendering.
- `opendream/static/observe-ui.css` owns tab styling.
- `tests/test_webapp_graph_route.py` owns static route/label regression coverage.

## Rollback
Restore the sidebar link and SPA routes to the previous `/memories` and `/semantic-changes` entrypoints; backend payload changes are independent.

## Verification
- `python3 -m unittest tests/test_observability.py tests/test_webapp_graph_route.py -v`
- `make test`
- `make verify`
