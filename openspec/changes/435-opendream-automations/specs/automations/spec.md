# Automation projections

## Requirements

### Requirement: managed automation jobs
OpenDream MUST let operators register schema-valid automation jobs with explicit trigger, selector, merge, decay, review, and security policy fields.

#### Scenario: register a job
- **WHEN** an operator registers a valid automation spec
- **THEN** OpenDream stores it under the workspace memory root
- **AND** validates the spec before accepting it

### Requirement: separate automation records
OpenDream MUST write automation outputs to a store that is separate from canonical durable memory.

#### Scenario: run a job
- **WHEN** a registered job executes successfully
- **THEN** OpenDream writes typed automation records and run state under the automation subtree
- **AND** durable memory records remain unchanged

### Requirement: top-level visibility
OpenDream MUST expose automation health through status and MAY include active automation projections in prepared context.

#### Scenario: inspect status
- **WHEN** an operator runs top-level status after automation jobs exist
- **THEN** the response includes an automation summary with due, healthy, and stale work counts
