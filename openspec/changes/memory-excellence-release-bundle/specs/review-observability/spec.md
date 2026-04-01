# review-observability/spec.md

## Requirements

### Requirement: reviewable truth state
Observability and review surfaces MUST expose why a memory is active, contested, superseded, or quarantined.

#### Scenario: inspect memory detail
- **WHEN** an operator opens a memory detail
- **THEN** claim provenance, relation edges, and verification outcomes are visible

### Requirement: probe and reconciliation visibility
Observability MUST expose transcript probe traces and reconciliation outcomes.

#### Scenario: inspect a dream run
- **WHEN** an operator inspects a run
- **THEN** they can see which probes fired, what windows were read, and whether reconciliation altered downstream state
