## ADDED Requirements

### Requirement: Aggregated status surface
The system MUST provide a top-level aggregated status response with a single next action when the setup is unhealthy.

#### Scenario: Status reports the next fix
- **GIVEN** a workspace has activation or runtime drift
- **WHEN** the operator runs `opendream status`
- **THEN** the response includes aggregated target and runtime state
- **AND** recommends one next action
