# contradiction-graph/spec.md

## Requirements

### Requirement: explicit relation edges
OpenDream MUST store explicit relation edges for contradiction, supersession, derivation, and verification.

#### Scenario: inspect related records
- **WHEN** two records conflict or one supersedes another
- **THEN** the relation is represented explicitly and audibly

### Requirement: relation-aware retrieval
Retrieval MUST use relation state.

#### Scenario: superseded record matches query
- **WHEN** a superseded record would otherwise rank highly
- **THEN** relation-aware scoring demotes it or surfaces it with warning rather than treating it as active truth
