# plan.md — 442-observe-health-and-live-check

## Summary
Extend observe serve with a first-class health contract and a synthetic end-to-end check. Keep the contract small, evidence-based, and local-first.

## Architecture impact
- touched components:
  - observe web handler
  - observability overview/index helpers
  - overview UI shell
  - tests and seeded fixtures
- unchanged components:
  - durable memory record format
  - retrieval and consolidation semantics

## Contract changes
- add `GET /api/health`
- add `POST /api/health/live-check`
- expose health evidence on the overview surface while preserving existing `/api/overview`

## API rules
- health responses must derive from the current store and observability index
- reasons must explain non-ready states instead of collapsing them into a single boolean
- live-check writes must use schema-valid events and must not create durable memory

## Rollout
1. define the health contract in code and tests
2. implement live-check probe append and refresh path
3. surface health evidence and action controls in the overview UI
4. update README observe-serve usage
5. rerun verification

## Rollback
1. remove health endpoints and overview control
2. keep freshness fields in overview if still useful

## Verification plan
- run: `python3 -m unittest tests.test_observability tests.test_webapp_graph_route`
- run: `make verify`
- manual checks:
  - `GET /api/health`
  - `POST /api/health/live-check`
  - overview page reflects the new probe

## ADR needed?
- no
