## ADDED Requirements

### Requirement: Zero-touch activation command
The system MUST provide `opendream activate` to detect configured supported agents in the workspace and install their managed activation surfaces.

#### Scenario: Configured targets are activated
- **GIVEN** a workspace contains supported configured agent surfaces
- **WHEN** the operator runs `opendream activate --workspace <path> --targets configured`
- **THEN** OpenDream installs the managed surfaces for those targets
- **AND** emits a machine-readable activation report

### Requirement: Idempotent activation
The system MUST keep activation idempotent when the managed surfaces are already current.

#### Scenario: Activation is rerun without drift
- **GIVEN** a workspace already has current managed activation surfaces
- **WHEN** the operator reruns `opendream activate`
- **THEN** OpenDream does not duplicate managed content
- **AND** reports a `noop` activation status
