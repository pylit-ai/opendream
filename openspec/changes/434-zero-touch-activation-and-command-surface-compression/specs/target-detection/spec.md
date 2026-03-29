## ADDED Requirements

### Requirement: Target registry for compressed status
The system MUST persist a target registry that tracks configured, activated, drifted, and unhealthy states for compressed status reporting.

#### Scenario: Status reads the registry
- **GIVEN** activation has run in a workspace
- **WHEN** the operator runs `opendream status`
- **THEN** status reads persisted target state and current runtime signals
- **AND** reports the resulting activation health
