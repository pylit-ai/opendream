# learned-context-layer/spec.md

## Requirements

### Requirement: separate learned-context storage
OpenDream MUST persist learned-context separately from typed durable fact/procedural memory.

#### Scenario: inspect memory state
- **WHEN** an operator inspects the memory store
- **THEN** learned-context records can be enumerated independently of durable records

### Requirement: provenance and freshness
Each learned-context record MUST include provenance and freshness metadata.

#### Scenario: retrieve a learned-context record
- **WHEN** a learned-context record is loaded
- **THEN** it exposes source ids, provider/model identity, creation time, freshness window, and verifier status
