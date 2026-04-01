# 03-anticipation-query-families.md

## Goal

Approximate the key Sleep-time Compute mechanism by targeting offline synthesis toward **likely future query families**, rather than summarizing indiscriminately.

## Query-family sources
- repeated user asks in transcripts
- repeated coding-task archetypes
- repeated retrieval queries
- repeated automation jobs
- repeated failure/recovery patterns
- repo-local guidance files and commands
- explicit operator-configured task families

## Query-family schema
Each family should include:
- `family_id`
- `title`
- `description`
- `examples`
- `source_signals`
- `predicted_frequency`
- `predicted_value`
- `freshness_window`
- `allowed_memory_types`
- `success_metrics`

## Anticipation algorithm
1. cluster recent tasks and retrieval queries
2. score by recurrence, strategic value, and latency sensitivity
3. select top-N families under budget
4. pass them into semantic dream prompts as targets
5. write learned context tagged by family
6. score downstream usefulness in benchmarks and memory-hurt audits

## Operator controls
- static family manifests
- dynamic family discovery
- family allow/deny lists
- family-level budgets
- family-specific prompts or examples
