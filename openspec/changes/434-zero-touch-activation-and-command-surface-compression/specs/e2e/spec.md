## ADDED Requirements

### Requirement: Standard-path release verification
Release verification MUST prove the compressed standard path for configured supported targets.

#### Scenario: Fixtures pass from init, status, repair, and deactivate
- **GIVEN** fixture workspaces for supported targets
- **WHEN** release verification runs
- **THEN** activation, aggregated status, repair, and deactivate succeed from the standard path
- **AND** release fails if manual glue is still required
