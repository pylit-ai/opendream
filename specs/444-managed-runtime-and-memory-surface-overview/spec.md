# spec.md — 444-managed-runtime-and-memory-surface-overview

## Title
Managed background runtime and digestible memory-surface introspection

## Why
The overview page exposes useful runtime and memory-surface summaries, but operators need a dedicated Memories area that makes the current retained memory surface easier to inspect without overloading Overview.

## In scope
- dedicated Memories surface page
- Memory Explorer as the durable-record table/timeline/detail page
- Memory Changes as the learned-context change review page
- overview links into the dedicated memory surface
- compatibility routes for existing memory and semantic-change URLs

## Out of scope
- changing durable memory persistence
- changing consolidation or semantic promotion behavior
- graph-first navigation

## User-visible behavior
- The sidebar has one top-level Memories item.
- Memories contains Surface, Explorer, and Changes subviews.
- Surface shows durable active, contested, learned active, recently pruned, low-signal share, type mix, highlights, startup highlights, and last runtime effects.
- Explorer keeps table and timeline as layout modes.

## Acceptance criteria
- [x] AC-1: `/memories/surface`, `/memories/explorer`, and `/memories/changes` render from the observe SPA
- [x] AC-2: `/memories` and `/semantic-changes` remain compatible routes
- [x] AC-3: Overview links to the dedicated Memory Surface for detailed inspection
- [x] AC-4: sidebar exposes one top-level Memories item for the memory area
- [x] AC-5: route/static tests cover the new IA labels and compatibility paths

## Required verifiers
- unit tests: yes, static bundle route needles
- integration tests: yes, observe HTML/API route coverage
- manual verification: yes, serve observe UI and navigate Surface, Explorer, and Changes
