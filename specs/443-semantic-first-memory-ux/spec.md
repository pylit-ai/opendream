# spec.md — 443-semantic-first-memory-ux

## Title
Semantic-first posture, progressive memory disclosure, and pruning proof

## Why
Operators need the observe UI and CLI to distinguish durable memory activity from learned-context semantic activity. Empty semantic surfaces must explain whether semantic memory is disabled, not materialized, or simply unavailable for the selected context, without implying that the workspace has no memory.

## In scope
- status and observe UI states for semantic-ready, degraded, and deterministic-by-choice modes
- memory-quality warnings for homogeneous or low-signal memory surfaces
- prompt-context progressive-disclosure and pruning metadata
- semantic-change empty states with explicit unavailable reasons
- compatibility links for pre-existing semantic-change routes

## Out of scope
- remote semantic provider orchestration beyond existing setup/status surfaces
- automatic promotion of learned context without verification
- schema or data migrations

## User-visible behavior
- Operators can tell when durable memory exists but learned-context comparison is unavailable.
- The UI explains why semantic change review is empty and provides concrete next actions.
- Timeline remains a view mode inside the memory explorer.

## Acceptance criteria
- [x] AC-1: top-level status and observe UI distinguish semantic-ready, degraded, and deterministic-by-choice states
- [x] AC-2: homogeneous-memory fixtures trigger memory-quality warnings instead of a healthy semantic verdict
- [x] AC-3: prepare-context emits progressive-disclosure and pruning metadata
- [x] AC-4: semantic-change unavailable states include reason code, counts, semantic mode, semantic capability state, and next actions
- [x] AC-5: compatibility routes for semantic changes remain usable

## Required verifiers
- unit tests: yes, semantic-readiness and unavailable payload construction
- integration tests: yes, observe API and UI route tests
- manual verification: yes, serve a deterministic workspace and inspect Memory Changes empty state
