# spec.md — 417-memory-review-and-fidelity-tooling

## Title
Add review workflows and fidelity diagnostics that make AutoDream-like behavior falsifiable

## Why
The MVP UI makes current state visible, but the point of this product is not generic observability. OpenDream needs review tooling and fidelity diagnostics that surface the four-phase dream lifecycle, lean index budget, transcript-vs-event coverage, activation diagnostics, and human-in-the-loop actions without hiding uncertainty.

## In scope
- review queue for contested, low-confidence, frequently suppressed, failed-run, suspicious retrieval, large-diff, and downvoted items
- explicit review actions: approve, suppress, split, merge, mark stale, attach note, escalate
- provenance graph as a secondary explanation surface with capped neighborhoods and temporal filtering
- fidelity diagnostics for four-phase runs, transcript-vs-event coverage, lean-index budget, activation diagnostics, and guardrail indicators
- eval and health views for retrieval latency, hit rate, contradiction rate, contested backlog, startup-index budget use, and manual review outcomes
- export builder for filtered memories, runs, traces, annotations, and diffs

## Out of scope
- arbitrary auto-merge or hidden write workflows
- whole-universe graph rendering
- replacing CLI eval flows
- unaudited export or sharing

## User-visible behavior
- Operators can triage contested or suspicious items from a queue before performing edits.
- Humans can inspect a consolidation run as the explicit four-phase lifecycle and measure transcript-derived versus event-derived signal coverage.
- The app exposes lean-index growth and guardrail state instead of only aggregate counters.
- Review actions, annotations, exports, and escalations remain explicit and auditable.

## Acceptance criteria
- [x] AC-1: review queue categories and actions exist with actor, rationale, and timestamp capture
- [x] AC-2: run detail exposes the explicit four-phase dream lifecycle with inputs, outputs, durations, warnings, and files consulted
- [x] AC-3: fidelity diagnostics expose transcript-vs-event coverage, activation diagnostics, and startup-index budget growth over time
- [x] AC-4: provenance graph supports focused neighborhood expansion, temporal filtering, side panels, and subgraph export without rendering the whole corpus
- [x] AC-5: eval and export surfaces support reproducible offline analysis with redaction and audit constraints

## Edge cases
- review actions against already-superseded records
- missing transcript-derived coverage data in historical runs
- deeply connected lineage nodes that exceed graph caps
- exports containing sensitive traces that require redaction
- failed runs with only partial phase traces

## Required verifiers
- unit tests: yes, review state transitions and fidelity-metric aggregation
- integration tests: yes, review actions, graph focus queries, export generation, and diagnostics rendering
- evals / scenario checks: yes, transcript-vs-event coverage and review-queue triage flows
- manual verification: yes, inspect a run for fidelity gaps and perform an auditable review action

## Risks
- fidelity metrics become decorative rather than falsifiable
- review actions mutate state without enough evidence or audit context
- graph tooling overwhelms the primary list-and-diff workflow

## Links
- `../416-memory-observability-webapp-mvp/spec.md`
- `../../notepads/active/openspec_webapp_autodream_introspection_bundle.md`
