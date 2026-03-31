# guidance-contracts/spec.md

## ADDED Requirements

### Requirement: path-scoped guidance
OpenDream MUST support path-scoped guidance surfaces that refine root guidance without becoming competing policy sources.

#### Scenario: enter a runtime subtree
- **WHEN** a coding agent works under `opendream/`
- **THEN** the agent can read subtree guidance specific to runtime changes
- **AND** canonical precedence remains documented and testable

### Requirement: stable contract export
OpenDream MUST export a stable machine-readable contract for agent clients.

#### Scenario: export the contract
- **WHEN** an operator runs `opendream contract export`
- **THEN** OpenDream emits a versioned JSON document listing commands, schemas, output versions, and example payloads
- **AND** the document validates against a contract schema

### Requirement: version-aware fixtures
OpenDream MUST keep contract fixtures synchronized with output-version changes.

#### Scenario: change an output field
- **WHEN** a stable JSON output shape changes
- **THEN** the contract fixture and version metadata must be updated
- **AND** verification must fail if that synchronization is missing
