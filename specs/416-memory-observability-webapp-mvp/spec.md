# spec.md — 416-memory-observability-webapp-mvp

## Title
Ship a read-only, desktop-first observability web app for memory state, runs, retrievals, and context

## Why
The observability APIs still leave operators reading JSON. OpenDream needs a desktop-first UI that makes memory state, retrieval assembly, and consolidation diffs legible in minutes without falling back to graph theatrics or vanity metrics.

## In scope
- shell, navigation groups, and route structure for overview, memories, sessions, runs, retrievals, context, reviews, evals, exports, graph, and settings
- overview page with health, counts, recent sessions, recent runs, and lock state
- memory explorer with searchable table, split-pane detail, filters, sorting, compare, and raw JSON
- run list and consolidation inspector with phase timeline, op log, diff viewer, and cross-links
- retrieval detail, context viewer, and session timeline
- URL-addressable filters and stable deep links

## Out of scope
- graph editing
- broad write actions beyond annotations if needed for MVP
- advanced review tooling beyond basic queue visibility
- production multi-user auth

## User-visible behavior
- Humans can inspect memory state, a retrieval, or a consolidation run without reading raw files.
- The UI privileges searchable lists, timelines, and diff views over graph-first navigation.
- Memory, run, retrieval, and session detail pages cross-link to one another and expose raw JSON and raw diff data.
- The app remains useful on large local datasets through indexed queries and capped graph behavior.

## Acceptance criteria
- [ ] AC-1: routes exist for overview, memories, memory detail, sessions, session detail, runs, run detail, retrievals, retrieval detail, context detail, reviews, evals, exports, graph, and settings
- [ ] AC-2: memory explorer supports full-text search, filters, sorting, split-pane detail, compare, visible status badges, and raw JSON
- [ ] AC-3: consolidation inspector shows the phase timeline, op log, diff viewer, and cross-links to source candidates and resulting records
- [ ] AC-4: retrieval detail and context viewer show selected memory objects, assembled context payload, omitted candidates, and omission reasons
- [ ] AC-5: session timeline renders user turns, assistant turns, tool calls, retrievals, consolidation triggers, consolidation ops, and annotations chronologically

## Edge cases
- datasets with 10k memories and 100k events
- missing diff artifacts for a historical run
- retrievals without omission data
- sessions whose linked runs were pruned
- direct links into empty or deleted records

## Required verifiers
- unit tests: yes, route-level rendering and component state behavior
- integration tests: yes, page data loading, filter URL sync, cross-linking, and empty-state handling
- evals / scenario checks: yes, navigation flows for memory inspection and run inspection
- manual verification: yes, answer core operator questions from the UI in under five minutes

## Risks
- the UI hides raw evidence behind summaries
- tables and timelines become unusable on larger local datasets
- deep links or filters drift from API semantics

## Links
- `../415-memory-observability-api-surface/spec.md`
- `../../notepads/active/openspec_webapp_autodream_introspection_bundle.md`
