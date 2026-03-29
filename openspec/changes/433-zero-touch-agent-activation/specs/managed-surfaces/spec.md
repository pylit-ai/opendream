## ADDED Requirements

### Requirement: Managed native surfaces
The system MUST install managed surfaces into actual agent-consumed config locations while preserving unrelated user content.

#### Scenario: Managed surfaces preserve surrounding content
- **GIVEN** a workspace already contains user-authored AGENTS or JSON hook config
- **WHEN** activation installs or repairs managed surfaces
- **THEN** OpenDream only updates its managed block or managed hook entries
- **AND** leaves unrelated content intact
