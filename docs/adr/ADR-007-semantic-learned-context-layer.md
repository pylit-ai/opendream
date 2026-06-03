# ADR-007: Semantic learned-context layer

## Status
Accepted

## Context
Sleep-time compute introduces offline semantic synthesis where models generate abstractions, summaries, and inferred relationships from durable memory during idle periods. These model-generated outputs are useful for enriching retrieval but differ fundamentally from canonical durable records: they go stale faster, may contain non-canonical inferences, and require an independent freshness policy. Mixing them into the existing durable-record store would weaken the integrity controls of the canonical memory layer.

## Decision
Introduce a separate learned-context layer for model-generated semantic abstractions. Learned-context records are stored under `memory/learned_context/`, distinct from `memory/state/durable_records.json`. Each record carries:
- provenance metadata (source records, generation timestamp, model version)
- a freshness TTL and staleness policy
- a promotion status (proposal, verified, promoted, stale)

Learned context is never written directly to the canonical durable store. It is surfaced as a separate retrieval source with explicit attribution.

## Consequences
- New storage path `memory/learned_context/` with its own schema and index
- New record type `learned_context_record` in the type system
- Retrieval must consult an additional source and attribute results accordingly
- Audit trail extends to cover learned-context generation, verification, and expiry
- Freshness policy can be tuned independently of durable-record lifecycle
- Stale learned context can be garbage-collected without affecting canonical state

## Alternatives considered
- Store learned context as a subtype of durable records (rejected: conflates canonical and inferred data, complicates trust boundaries)
- Keep learned context only in ephemeral prompt cache (rejected: loses cross-session value, prevents verification)

## References
- ADR-002: Layered memory store precedence
- Sleep-time Compute paper (Luo et al., 2025)
