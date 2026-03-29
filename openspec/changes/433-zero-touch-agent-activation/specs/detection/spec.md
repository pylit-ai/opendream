## ADDED Requirements

### Requirement: Agent detection and registry
The system MUST detect supported configured agents from repo-local evidence and persist registry state under `.opendream/`.

#### Scenario: Detection persists target state
- **GIVEN** a workspace contains one or more supported agent config roots
- **WHEN** activation or doctor runs
- **THEN** OpenDream writes registry state describing configured, activated, and drifted targets
- **AND** does not guess destructive paths outside the workspace
