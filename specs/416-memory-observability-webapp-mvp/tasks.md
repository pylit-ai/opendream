# tasks.md — 416-memory-observability-webapp-mvp

## Rules
- Execute in order unless marked [P].
- Update this file as work completes.
- Do not mark complete unless the verifier for that item has passed.

## Tasks
- [x] T1: add `416-memory-observability-webapp-mvp` to `specs/registry.yaml`
- [x] T2: scaffold the web app shell, route tree, and API client bindings
- [x] T3: implement overview, memory explorer, and memory detail
- [x] T4: implement runs list, consolidation inspector, and diff viewer
- [x] T5: implement retrieval detail, context viewer, and session timeline
- [x] T6: add URL-addressable filters, compare flows, and stable deep links
- [x] T7: add frontend tests and seeded fixtures for empty and populated states
- [x] T8: update docs with local run instructions for the observability UI
- [x] T9: run `make verify`
- [x] T10: reconcile implementation against acceptance criteria

## Parallelizable
- [x] [P] TP1: table and filter-state component work
- [x] [P] TP2: diff-viewer and timeline component work

## Completion checklist
- [x] all acceptance criteria satisfied
- [x] no constitution violations
- [x] raw evidence remains visible from every detail surface
