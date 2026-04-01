# status-observability/spec.md

## Requirements

### Requirement: semantic execution visibility
OpenDream MUST expose active semantic execution strategy and auth source in operator status surfaces.

#### Scenario: inspect semantic status
- **WHEN** an operator runs `opendream semantic status`
- **THEN** the output includes active strategy, auth source, candidate strategies, and remediation hints

### Requirement: delegated runtime observability
OpenDream MUST expose delegated run/ingest state in observability surfaces.

#### Scenario: inspect recent runs
- **WHEN** an operator opens the observability surface
- **THEN** they can distinguish local direct-provider runs from Codex-, Claude-, and Cursor-owned runs
