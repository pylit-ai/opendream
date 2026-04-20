# 03-status-doctor-and-contract.md

## Goal

Expose semantic readiness and memory quality through one coherent operator contract across CLI, API, and machine-readable exports.

## Required read-model fields

- `product_posture`
- `semantic_capability_state`
- `active_execution_strategy`
- `semantic_unavailability_reason`
- `last_semantic_run`
- `learned_context_count`
- `memory_quality`
- `context_pruning`
- `next_action`

## Memory-quality diagnostics

Diagnostics MUST detect and explain at least:
- semantic configured but unavailable
- zero learned-context records after a configurable semantic-first observation window
- homogeneous durable memory dominated by one type
- high ephemera ratio in recent promoted memory
- stale pending or waiting-style memory that should have remained suppressed or decayed
- no meaningful pruning delta between raw candidates and injected prompt context

## Doctor surfaces

- top-level `status` remains the primary answer and SHOULD summarize only the highest-signal diagnosis
- `workspace doctor` or an equivalent machine-readable doctor surface SHOULD expose the full warning set with remediation
- `contract export` SHOULD include the same readiness and quality fields so agents and dashboards can consume them programmatically

## Fixture requirement

The repo MUST include a homogeneous-memory fixture representing the failure mode where:
- semantic posture is requested
- no semantic provider or adapter is actually available
- durable memory is almost entirely `semantic_fact`
- learned-context count remains zero

That fixture is the minimum regression case for this bundle.
