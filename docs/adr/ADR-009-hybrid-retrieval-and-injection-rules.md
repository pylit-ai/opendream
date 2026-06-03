# ADR-009: Hybrid retrieval and injection rules

## Status
Accepted

## Context
With the addition of learned context (ADR-007), the retrieval system now draws from multiple memory sources: durable facts, procedural memory, learned context, and automation projections. These sources have different trust levels, freshness profiles, and relevance characteristics. Without explicit ranking and attribution rules, retrieval results could silently mix canonical facts with inferred content, creating confusion about provenance and reliability.

## Decision
Retrieval fuses all available memory sources with per-source attribution. Ranking and conflict resolution follow these rules:

- **Durable facts outrank learned context** on direct factual conflict.
- **Learned context may outrank raw facts** when the query family is strongly matched, freshness is high, and no direct contradiction exists.
- **Automation projections** are included with explicit `[projection]` attribution and never override durable facts.
- **Procedural memory** (how-to, workflow patterns) is scored by recency and match strength.

Every retrieval result includes source attribution indicating the originating layer. Context assembly tags each injected block with its source type. Harm-aware suppression filters prevent injection of learned context that has been flagged during verification (ADR-008).

## Consequences
- Extended retrieval scoring incorporates source-type weighting alongside existing lexical, semantic, and recency signals
- Per-source attribution in assembled context enables downstream consumers to reason about reliability
- Harm-aware suppression adds a safety layer for flagged content
- Retrieval explanations (existing feature) extend to cover source-type rationale
- Increased complexity in scoring; mitigated by clear precedence rules and test coverage

## Alternatives considered
- Flat ranking across all sources (rejected: obscures trust differences between canonical and inferred content)
- Separate retrieval endpoints per source (rejected: fragments the query experience, pushes fusion burden to consumers)

## References
- ADR-007: Semantic learned-context layer
- ADR-008: Semantic verifier and promotion policy
- ADR-002: Layered memory store precedence
