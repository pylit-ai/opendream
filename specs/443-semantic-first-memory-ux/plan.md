# plan.md — 443-semantic-first-memory-ux

## Approach
- Preserve the existing semantic-change review payload when comparable learned-context data exists.
- Add an explicit unavailable payload for latest semantic-change review when learned-context comparison cannot be built.
- Keep explicit unknown semantic-change source IDs as 404s.
- Surface unavailable reasons in the observe UI using status regions and concrete next actions.

## Files
- `opendream/observability.py` owns payload construction and overview summary fields.
- `opendream/webapp.py` owns HTTP status behavior.
- `opendream/static/observe-ui.js` owns route rendering and empty-state copy.
- `tests/test_webapp_graph_route.py` and `tests/test_observability.py` own regression coverage.

## Rollback
Revert the unavailable-payload branch and UI route changes; compatibility routes allow old links to continue working during rollback.

## Verification
- `python3 -m unittest tests/test_observability.py tests/test_webapp_graph_route.py -v`
- `make test`
- `make verify`
