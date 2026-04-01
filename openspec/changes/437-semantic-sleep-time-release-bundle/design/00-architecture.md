# 00-architecture.md

## Decision

Extend OpenDream into a **hybrid memory runtime** with four distinct but connected layers:

1. **Evidence layer**
   - immutable events
   - transcript episodes
   - automation outcomes
   - task traces

2. **Canonical durable layer**
   - typed fact / preference / procedural / environment records
   - contradiction, supersession, quarantine, and review state

3. **Learned-context layer**
   - model-generated semantic abstractions targeted at future query families
   - versioned, attributable, freshness-aware, and explicitly non-canonical until promoted

4. **Projection / automation layer**
   - backlog/radar/strategist outputs
   - semantic refresh and task-oriented maintenance jobs

## Why this architecture

It preserves existing OpenDream strengths:
- local-first inspectability
- single-writer safety
- typed durable records
- auditable promotion and diff artifacts
- bounded explicit DreamRunner lifecycle

while adding the missing performance mechanism:
- offline semantic anticipation
- amortized precompute for likely future tasks
- learned context that can improve task-time performance without replacing canonical memory

## Key invariants

- semantic memory is useful, not sovereign
- durable facts remain typed and source-grounded
- learned context must be attributable and freshness-scored
- model output never silently mutates canonical state
- every promotion path has an audit record
