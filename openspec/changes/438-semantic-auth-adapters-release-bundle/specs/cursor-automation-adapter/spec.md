# cursor-automation-adapter/spec.md

## Requirements

### Requirement: Cursor automation delegated semantic execution
OpenDream MUST support a Cursor adapter that runs semantic refresh through Cursor Automations and returns results via delegated ingest.

#### Scenario: account-backed automation path
- **WHEN** Cursor is configured and the operator prefers no-extra-key setup
- **THEN** OpenDream recommends the account-backed automation path over the programmatic API-key path
- **AND** can scaffold the automation prompt/instructions and return-path artifact layout

### Requirement: artifact-in-repo return path
Cursor delegated semantic runs MUST use a bounded artifact return path that OpenDream can validate and ingest.

#### Scenario: automation writes result
- **WHEN** a Cursor automation completes
- **THEN** it writes a valid delegated semantic envelope to the configured inbox path
- **AND** OpenDream ingests it on the next scan or explicit ingest command
