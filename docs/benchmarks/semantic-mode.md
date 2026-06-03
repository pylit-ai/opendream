# Semantic-Mode Benchmark Expectations

This document defines what OpenDream must prove before semantic-first claims are credible in benchmarks and verification checks.

## Core rule

Semantic-first is a **posture**. Benchmark evidence must distinguish:

- **semantic-ready**: a runnable semantic path exists and the system shows context-pruning benefit with no repeated-task regression
- **degraded semantic-first**: semantic posture is requested but no runnable semantic path is available, so OpenDream reports the degraded reason and next action while falling back explicitly
- **deterministic-by-choice**: the operator explicitly chose deterministic mode, which is not a degradation

`mode=semantic` alone is never enough to score a workspace as semantic-ready.

## Required benchmark slices

Benchmark reports should include at least these slices:

1. **Unpruned baseline**: comparable retrieval without semantic-first progressive disclosure so prompt-bloat cost is visible.
2. **Degraded semantic-first**: semantic posture requested, semantic path unavailable, deterministic fallback labeled truthfully.
3. **Semantic-ready progressive**: runnable semantic path plus progressive disclosure that injects a smaller, more relevant context.

## What must be measured

Semantic-mode proof is not just "an LLM-related path executed." Benchmarks should measure:

- raw candidate count before pruning
- injected record count after pruning
- token or character budget savings
- suppressed or penalized record counts when available
- repeated-task outcome evidence beyond context shrinkage alone
- degraded-state labeling accuracy when semantic capability is unavailable

## Memory-quality expectations

Benchmarks should fail healthy-semantic expectations when the workspace shows low-signal memory behavior, including:

- recent durable memory dominated by a single low-signal type such as `semantic_fact`
- no learned-context activity across the observation window
- ephemera-heavy promoted memory
- no measurable pruning advantage compared with the unpruned baseline

Those are memory-quality warnings, not acceptable semantic-ready outcomes.

## Operator-facing interpretation

When a benchmark lands in degraded semantic-first, the user-facing interpretation should be:

- semantic-first posture is active
- readiness is not yet achieved
- deterministic fallback remained available
- the degraded reason and next action were explicit

When a benchmark lands in semantic-ready progressive mode, the user-facing interpretation should be:

- the readiness claim was backed by a runnable semantic path
- progressive disclosure pruned context in an inspectable way
- repeated-task behavior stayed flat or improved

## Verification Intent

`make release-check` should fail if OpenDream cannot show both of the following:

- truthful degraded labeling when semantic posture is requested but unavailable
- a measurable pruning advantage for semantic-ready progressive disclosure without worse repeated-task results
