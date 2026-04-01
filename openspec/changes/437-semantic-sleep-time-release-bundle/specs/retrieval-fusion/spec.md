# retrieval-fusion/spec.md

## Requirements

### Requirement: multi-source retrieval
OpenDream MUST retrieve across durable facts, procedural memory, learned context, and automation projections.

#### Scenario: prepare context
- **WHEN** `prepare-context` runs
- **THEN** selected record ids are exposed per source category

### Requirement: source attribution
Injected semantic memory MUST be attributable.

#### Scenario: learned context is injected
- **WHEN** a learned-context record is added to prompt context
- **THEN** the output identifies it as learned context and surfaces freshness/caveat metadata when needed

### Requirement: harm-aware suppression
OpenDream MUST suppress or de-prioritize stale/contradicted learned context.

#### Scenario: stale record matches query
- **WHEN** a stale learned-context record scores highly lexically
- **THEN** freshness/harm policy can suppress or downgrade it
