# e2e-release/spec.md

## ADDED Requirements

### Requirement: end-to-end conformance
OpenDream MUST provide end-to-end verification for package generation, contract export, engine-backed automation execution, and isolated code-mutation runs.

#### Scenario: run the release gate
- **WHEN** an operator runs the full verification command
- **THEN** all conformance checks execute
- **AND** the release is blocked if any required gate fails

### Requirement: migration compatibility
OpenDream MUST provide migration guidance and compatibility behavior for existing adapter and automation users.

#### Scenario: upgrade from the current repo state
- **WHEN** an operator upgrades to the new platform
- **THEN** existing supported flows continue to work or emit explicit migration guidance
- **AND** no silent behavior fork occurs
