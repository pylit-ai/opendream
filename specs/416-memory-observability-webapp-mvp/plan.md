# plan.md — 416-memory-observability-webapp-mvp

## Summary
Build the read-only observability UI first. Prioritize overview, memory explorer, runs, retrievals, context, and session timelines before advanced review or graph tooling.

## Architecture impact
- touched components:
  - new web application shell and routes
  - API client and contract bindings
  - table, diff-viewer, and timeline components
  - tests and seeded UI fixtures
- unchanged components:
  - memory runtime behavior
  - source-of-truth file layout

## Route map
- `/overview`
- `/memories`
- `/memories/:memoryId`
- `/sessions`
- `/sessions/:sessionId`
- `/runs`
- `/runs/:runId`
- `/retrievals`
- `/retrievals/:retrievalId`
- `/context/:contextId`
- `/graph`
- `/reviews`
- `/evals`
- `/exports`
- `/settings`

## UX rules
- default to searchable lists and timelines
- raw JSON and raw diff are always available
- filters are URL-addressable
- compare is side-by-side and explicit
- graphs are secondary, not the homepage

## Rollout
1. add spec and registry entry
2. scaffold shell and route structure
3. implement overview and explorer surfaces
4. implement run, retrieval, context, and session detail
5. add deep-linking, diff view, and performance constraints
6. rerun verification

## Rollback
1. remove the web app
2. keep APIs and read model intact

## Verification plan
- run: frontend test suite
- manual checks:
  - answer why a memory exists from the UI
  - inspect what changed in the last run
  - inspect what the agent saw for a retrieval or turn

## ADR needed?
- no
