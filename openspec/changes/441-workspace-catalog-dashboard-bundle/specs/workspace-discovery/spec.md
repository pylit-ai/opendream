# workspace-discovery/spec.md

## Requirements

### Requirement: explicit root scans
OpenDream MUST only scan operator-configured roots or explicitly supplied scan roots.

#### Scenario: no roots configured
- **WHEN** an operator requests a root scan with no configured roots
- **THEN** OpenDream returns an explicit result with remediation
- **AND** does not silently scan broad default paths

### Requirement: event-driven catalog updates
OpenDream SHOULD update the catalog when first-party workspace commands succeed.

#### Scenario: install service
- **WHEN** `install-service` succeeds for a workspace
- **THEN** the catalog entry updates its service summary
