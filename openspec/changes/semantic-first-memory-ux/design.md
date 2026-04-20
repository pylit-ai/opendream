## Context

OpenDream already has semantic execution, delegated ingest, observability, and compact generated memory views. The missing layer is a product contract that makes those capabilities legible as semantic-first behavior instead of optional expert features. Existing active bundles provide truthful execution ownership and health evidence, but they do not yet make progressive disclosure, pruning, and memory-quality diagnosis central to the normal path.

This change builds on `440-advanced-memory-platform-release-bundle` and `442-observe-health-and-live-check` without redefining their lower-level execution or health contracts.

## Goals / Non-Goals

**Goals:**
- make semantic-first the default posture while preserving truthful degraded fallback
- expose progressive disclosure and pruning as inspectable context-assembly behavior
- add quality diagnostics for misleading or low-signal semantic workspaces
- make `/overview` and `/settings` the primary operator surfaces for semantic readiness and memory quality
- add release proof that semantic-ready mode saves context budget and preserves or improves repeated-task outcomes

**Non-Goals:**
- removing deterministic mode
- changing canonical memory storage from typed records to markdown
- introducing hidden remote memory or hidden semantic execution
- replacing raw JSON and evidence surfaces with UI-only summaries

## Decisions

### Decision: Semantic-first is a posture, not a truth claim
OpenDream will default new and repaired workspaces into a semantic-first posture, but readiness must be derived from actual runnable execution plus a valid return path. This preserves differentiation without violating the constitution's ban on silent or misleading fallbacks.

Alternative considered:
- keep deterministic default and offer semantic as an advanced option
Why rejected:
- it weakens product differentiation and hides the intended northstar behind expert setup.

### Decision: Progressive disclosure must be represented in contracts
`prepare-context`, status, and observe surfaces will expose profiles, budgets, suppression, and pruning deltas. This makes the semantic advantage measurable and debuggable.

Alternative considered:
- rely on invisible internal heuristics and only show final prompt text
Why rejected:
- operators and evaluators could not verify whether semantic mode is actually compressing useful context.

### Decision: Memory quality is part of readiness
A workspace that is syntactically configured for semantic mode but produces homogeneous or low-signal memory should not present as healthy. Quality diagnostics become part of operator truth, not a separate expert report.

Alternative considered:
- keep quality diagnostics in evals only
Why rejected:
- it allows week-long drift before users notice that semantic value is not materializing.

### Decision: Observe UI must lead with readiness and quality, not raw pipeline toggles
The header and settings page should surface the active semantic story first, with raw mode controls available behind disclosure. This aligns the web app with the compressed CLI contract.

Alternative considered:
- retain the existing mode selector as the primary affordance
Why rejected:
- it implies control without explaining whether the selected mode is actually runnable.

## Risks / Trade-offs

- [Risk] Semantic-first language could still be interpreted as a readiness claim.
  → Mitigation: enforce explicit `ready`, `degraded`, and `disabled_by_choice` states in CLI, API, and UI.
- [Risk] Additional status and quality fields could overcomplicate the normal path.
  → Mitigation: keep `status` high-signal and reserve detailed evidence for doctor, raw JSON, and expanded UI sections.
- [Risk] Pruning metrics could incentivize over-pruning.
  → Mitigation: release gates pair context-efficiency metrics with repeated-task outcome checks.
- [Risk] Web app scope could drift into a full memory IDE.
  → Mitigation: keep the UI centered on readiness, review, and context preview rather than full editing workflows.

## Migration Plan

1. extend the read models and contracts with readiness and quality fields
2. add progressive context-profile assembly and pruning metadata
3. add homogeneous-memory regression fixtures and doctor warnings
4. redesign observe header, overview, and settings surfaces
5. wire release checks for pruning advantage and truthful degraded labeling

## Open Questions

- whether the context-profile contract should live entirely inside existing `prepare-context` JSON or gain a dedicated schema file
- whether memory-quality diagnostics belong under `workspace doctor`, `status --json`, or both as first-class top-level blocks
- how strict the pruning-advantage release threshold should be across benchmark fixtures
