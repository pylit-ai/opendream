## ADDED Requirements

### Requirement: Doctor and repair
The system MUST diagnose activation drift and restore valid managed surfaces with one repair command.

#### Scenario: Missing managed surface is repaired
- **GIVEN** an activated workspace loses or drifts a managed surface
- **WHEN** the operator runs `opendream doctor --surface agents` followed by `opendream activate --repair`
- **THEN** doctor reports the drift
- **AND** repair restores the missing or drifted managed surface
- **AND** emits a machine-readable repair report
