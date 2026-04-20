# 444-managed-runtime-and-memory-surface-overview

## Why

OpenDream now has service lifecycle primitives, worker health, semantic posture, and a rich observability UI. The product gap is orchestration and legibility:

- the common path still depends on manual `dream run`, `tick`, or separate service installation to keep improvement happening
- operators can see health and readiness, but not a high-signal answer to "is background improvement actually running and what did it change?"
- the observe UI exposes detailed evidence, but not a digestible memory-surface snapshot that answers the state of durable memory in minutes

This bundle makes ongoing memory improvement part of the managed primary path and adds a clearer operator story around runtime control, dream effects, and memory state.

The follow-up gap discovered during dogfooding is that a managed worker can be alive without actually materializing semantic value. This bundle therefore also needs a semantic-aware auto mode and a first-class semantic-pipeline diagnosis so operators can tell whether the runtime is merely polling or actually converting recent signal into learned context.

## Goal

Ship an always-improving-by-default runtime posture in which:

- primary commands can ensure the background runtime is installed and running without requiring daemon knowledge
- operators can manage that runtime from both CLI and observe UI with explicit start, stop, restart, and opt-out controls
- overview surfaces show what dreaming changed, what the memory surface looks like now, and whether improvement is actually materializing

## What Changes

- add a shared "ensure background runtime" path that primary commands can call idempotently
- persist explicit background-runtime policy so operators can opt out while keeping the default path managed
- expose service policy, service health, and reversible controls in CLI and `/settings`
- add digestible overview panels for:
  - background runtime state
  - semantic pipeline state, including whether semantic signal is pending, blocked, or materialized
  - last dream / semantic-dream change summary
  - current memory-surface snapshot by typed active state, freshness, and low-signal concentrations
- keep detailed raw evidence and diff surfaces available behind the existing routes and APIs

## Non-goals

- hidden remote control planes or hosted orchestration
- silent code mutation outside the memory subtree
- removing the existing detailed observability surfaces
- replacing explicit service install/status commands for advanced operators

## Success Criteria

- a freshly initialized or upgraded workspace no longer needs recurring manual `dream run` or `tick` calls to keep background improvement active
- event-driven semantic-first workspaces no longer stall in a transcript-only worker loop; the managed runtime can consume explicit-event backlog and materialize learned context
- CLI and observe UI show the same runtime truth and offer the same operational controls
- overview makes it easy to answer:
  - is OpenDream improving this workspace right now?
  - is the semantic pipeline merely configured, actively waiting on signal, blocked, or already materializing learned context?
  - what changed in the last dream cycle?
  - what shape is the memory surface currently in?
