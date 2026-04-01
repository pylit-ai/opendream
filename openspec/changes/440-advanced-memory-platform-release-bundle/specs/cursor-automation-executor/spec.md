# cursor-automation-executor/spec.md

## Requirements

### Requirement: Cursor delegated automation execution
OpenDream MUST support a Cursor adapter that runs semantic work through Cursor Automations and returns a validated envelope.

#### Scenario: account-backed automation path
- **WHEN** Cursor is configured and no extra key is preferred
- **THEN** setup recommends the account-backed automation path and scaffolds it

### Requirement: bounded return path
Cursor delegated runs MUST return through a bounded artifact path.

#### Scenario: automation completes
- **WHEN** a Cursor automation emits a result
- **THEN** the result lands in the configured inbox path and validates before ingest
