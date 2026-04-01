# 04-index-discipline-and-compat-views.md

## Goal
Keep the startup index tiny, pointer-like, and mechanically regenerated.

## Rules
- canonical truth lives in typed durable records and relation metadata
- topic markdown and compat views are generated artifacts
- `MEMORY.md` is a pointer/index layer, not a mini knowledge base
- every pointer line should resolve to a durable record or topic id
- line budgets and character budgets are enforced
- topic/state updates occur before index regeneration

## Atomic write discipline
1. update durable/topic state
2. update relation edges and freshness metadata
3. regenerate `MEMORY.md` and compat views
4. emit audit artifacts

## Drift checks
Verification fails if generated views diverge from canonical state.
