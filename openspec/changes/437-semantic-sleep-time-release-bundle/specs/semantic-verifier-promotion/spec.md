# semantic-verifier-promotion/spec.md

## Requirements

### Requirement: proposal-only default
Semantic outputs MUST be proposal-only by default.

#### Scenario: semantic synthesis completes
- **WHEN** the synthesizer returns candidate learned context
- **THEN** those candidates are not immediately canonical
- **AND** they pass through verifier and promotion contracts first

### Requirement: verifier veto
Deterministic and semantic verifiers MUST be able to veto promotion.

#### Scenario: unsupported extrapolation detected
- **WHEN** a verifier detects unsupported extrapolation
- **THEN** promotion is blocked
- **AND** the rejection reason is audited

### Requirement: optional distillation
OpenDream MAY distill a verified learned-context output into typed durable candidates through an explicit, auditable path.

#### Scenario: learned context maps to a durable schema
- **WHEN** a verified learned-context output maps cleanly to an allowed durable record type
- **THEN** OpenDream emits a typed candidate with provenance linking back to the semantic output
