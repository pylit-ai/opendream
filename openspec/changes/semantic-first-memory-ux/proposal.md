# 443-semantic-first-memory-ux

## Why

OpenDream already has the underlying ingredients for semantic memory: learned-context records, execution-strategy setup, delegated semantic ingest, compact generated memory views, and observability surfaces. What it does not yet have is a sharp enough product contract around those capabilities.

Today a workspace can look "semantic" while still behaving like deterministic capture with a nicer label:
- semantic mode can be configured without a runnable semantic path
- homogeneous `semantic_fact` output can accumulate without strong quality warnings
- the web app exposes raw pipeline controls instead of one truthful operator answer
- context assembly does not yet make semantic pruning and progressive disclosure visibly central to the product promise

That gap matters because semantic mode is not differentiated merely by using an LLM. The differentiated value is that semantic dreaming should transform a larger, noisier history into **smaller, more relevant, better-pruned context** that improves repeated-task performance without surrendering auditability.

This follow-on bundle turns that product posture into an explicit, testable contract.

## Goal

Ship a semantic-first operator experience in which:
- `init`, `activate`, `status`, and observe surfaces default to a semantic-first posture
- unavailable semantic execution is shown as an explicit degraded state, not hidden behind a misleading mode label
- `prepare-context` and related read paths use progressive disclosure and pruning as first-class behavior
- operators can see memory-quality warnings, context-budget savings, and pruning effectiveness in both CLI and web UI
- release evidence proves semantic mode reduces prompt bloat while preserving or improving repeated-task outcomes

## What Changes

- make **semantic-first** the default product posture for new and repaired workspaces while preserving an explicit deterministic-by-choice path
- extend top-level status, workspace doctor, contract export, and observe APIs with:
  - semantic readiness / degraded state
  - active execution owner
  - last semantic run evidence
  - memory-quality diagnostics
  - context-pruning effectiveness
- add progressive context profiles so startup and task-time retrieval stay compact and expand only when relevance justifies it
- make pruning visible by reporting raw candidate counts versus injected record counts and token budgets
- add memory-quality heuristics and doctor warnings for:
  - semantic configured but unavailable
  - zero learned-context activity in semantic-first workspaces
  - low durable-type diversity
  - ephemera-heavy capture
  - no measurable pruning advantage
- redesign the observe web UI so `/overview` and `/settings` become the main semantic readiness, memory quality, and context-preview surfaces
- add benchmark and release gates that treat context efficiency and pruning quality as part of semantic-mode proof, not optional garnish

## Capabilities

- `semantic-first-posture`
- `progressive-context-disclosure`
- `memory-quality-diagnostics`
- `semantic-operator-ui`

## Non-goals

- removing deterministic mode as an explicit operator choice
- forcing provider keys or delegated adapters before any memory capture can happen
- injecting raw transcripts or full memory bodies into startup context by default
- replacing canonical typed state with markdown-first memory
- hiding raw JSON, logs, or evidence in the name of a cleaner UI

## Success criteria

- a fresh workspace defaults to semantic-first setup, and `status` reports either:
  - semantic ready,
  - semantic degraded with a concrete reason and next action,
  - or deterministic by explicit operator choice
- a seeded homogeneous-memory workspace triggers quality warnings in CLI and web UI instead of quietly presenting itself as healthy semantic memory
- `prepare-context` emits explicit profile, budget, pruning, and suppression metadata and keeps startup context pointer-like by default
- observe `/overview` and `/settings` show semantic readiness, quality warnings, pruning evidence, and links to raw artifacts without requiring docs archaeology
- release checks compare semantic progressive-disclosure behavior against an unpruned baseline and fail if semantic mode cannot show a context-efficiency win with no repeated-task regression
