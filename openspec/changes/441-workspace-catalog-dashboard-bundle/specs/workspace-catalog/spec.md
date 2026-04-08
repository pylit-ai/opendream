# workspace-catalog/spec.md

## Requirements

### Requirement: machine-local derived catalog
OpenDream MUST maintain a machine-local workspace catalog as derived state.

#### Scenario: initialize a workspace
- **WHEN** an operator initializes or activates a workspace
- **THEN** OpenDream can add or update a catalog entry for that workspace
- **AND** the catalog entry does not become canonical over the workspace-local state

### Requirement: stale/missing handling
OpenDream MUST preserve stale or missing entries diagnostically rather than deleting them silently.

#### Scenario: workspace path missing
- **WHEN** a known workspace path no longer exists
- **THEN** the catalog marks it missing or stale
- **AND** surfaces remediation
