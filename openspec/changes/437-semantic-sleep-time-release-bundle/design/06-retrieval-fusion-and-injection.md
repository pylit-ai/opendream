# 06-retrieval-fusion-and-injection.md

## Retrieval sources
1. durable fact / preference / environment records
2. procedural memory
3. learned-context records
4. automation projections

## Fusion rules
- durable facts outrank learned context on direct factual conflict
- procedural memory outranks learned context for exact workflow steps
- learned context may outrank raw facts when the query family is strongly matched and freshness is high
- automation projections remain non-canonical and should be clearly labeled

## Injection contract
`prepare-context` and related surfaces must be able to emit:
- `selected_durable_record_ids`
- `selected_learned_context_ids`
- `selected_automation_record_ids`
- source-labeled sections in `prompt_context`
- optional freshness / caveat footers when learned context is injected

## Harm controls
- stale learned-context penalty
- contradiction penalty
- irrelevant recall penalty
- per-query-family injection budget
- suppression when task is easy and retrieval gating says skip

## Why this matters
Semantic sleep-time is valuable only if the useful abstraction actually reaches the downstream task without drowning it in stale cleverness.
