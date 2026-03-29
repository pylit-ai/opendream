## ADDED Requirements

### Requirement: One-command repair remains primary
The system MUST keep `activate --repair` as the primary standard-path repair surface.

#### Scenario: Drift is repaired from the compressed path
- **GIVEN** a workspace has drifted managed activation surfaces
- **WHEN** the operator runs `opendream activate --repair`
- **THEN** OpenDream restores the managed state
- **AND** the compressed status view returns to healthy or degraded with one next action
