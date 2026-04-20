# 02-progressive-memory-disclosure-and-pruning.md

## Goal

Turn progressive disclosure and pruning into explicit runtime behavior instead of an implicit aspiration.

## Context profiles

`prepare-context` and related read surfaces SHOULD support explicit profiles:
- `startup`
- `task_light`
- `task_semantic`
- `task_deep`

## Profile rules

- `startup`
  - pointer-like only
  - prioritize decisions, workflows, environment constraints, and high-salience user preferences
  - include learned context only when freshness and query-family match justify it
- `task_light`
  - suppress retrieval when the task is easy or the query is weakly matched
  - prefer minimal direct pointers over expanded summaries
- `task_semantic`
  - admit a bounded learned-context and procedural-memory slice when semantic relevance is strong
  - enforce per-type and per-profile budgets
- `task_deep`
  - expand evidence only when explicitly requested or when the task crosses configured complexity thresholds

## Selection report

Every prompt-context assembly SHOULD emit inspectable metadata:
- selected record ids by type
- suppressed record counts and reasons
- raw candidate count before pruning
- final injected record count after pruning
- token/character budget used
- freshness and contradiction penalties applied
- next-expansion hints

## Pruning requirements

Semantic consolidation and context assembly MUST work together to:
- suppress stale or low-value status ephemera
- prevent a flat list of generic facts from dominating startup context
- favor higher-signal typed memory over repeated generic `semantic_fact` output
- show measurable reduction from raw candidate set to injected prompt context

## Why this is differentiated

Semantic mode is valuable partly because it can distill more history into less prompt space. If OpenDream cannot show that distillation and the resulting budget savings, it forfeits a central state-of-the-art advantage.
