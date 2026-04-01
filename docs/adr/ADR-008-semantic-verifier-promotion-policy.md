# ADR-008: Semantic verifier and promotion policy

## Status
Accepted

## Context
Model outputs from sleep-time compute cannot be trusted to directly mutate canonical state. Semantic abstractions may contain hallucinations, stale inferences, or contradictions with ground-truth durable records. A verification gate is needed before any model-generated content influences retrieval or downstream decisions.

## Decision
All semantic outputs are proposals first and must clear verification gates before promotion. The verification pipeline has two stages:

1. **Deterministic checks** (required): provenance validation, timestamp consistency, contradiction detection against durable records, schema conformance.
2. **Semantic checks** (optional, configurable): groundedness scoring against source records, compression quality assessment, redundancy detection.

Promotion follows an explicit state machine: `proposal` → `verified` → `promoted` → `stale`. Only `promoted` records are eligible for inclusion in retrieval results by default. Operators may configure retrieval to include `verified`-but-not-promoted records with explicit attribution.

## Consequences
- Two-stage verification is the default path for all learned-context records
- Proposal-only default prevents unverified content from polluting retrieval
- Explicit state machine makes promotion auditable and reversible
- Semantic checks can be enabled or disabled per deployment without breaking the pipeline
- Adds latency between generation and availability; acceptable for offline compute

## Alternatives considered
- Trust model outputs directly (rejected: no safety boundary against hallucination)
- Human-only review gate (rejected: does not scale for high-volume sleep-time runs)
- Single-stage verification without semantic checks (rejected: misses groundedness issues that deterministic checks cannot catch)

## References
- ADR-007: Semantic learned-context layer
- ADR-002: Layered memory store precedence
