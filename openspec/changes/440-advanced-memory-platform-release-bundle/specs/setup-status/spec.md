# setup-status/spec.md

## Requirements

### Requirement: setup wizard
OpenDream MUST provide a setup wizard that recommends a supported strategy.

#### Scenario: prefer no-extra-key
- **WHEN** an operator runs `opendream semantic setup --prefer no-extra-key`
- **THEN** OpenDream returns one recommended strategy with reasons and next steps

### Requirement: machine-readable report
The setup wizard MUST emit a report artifact.

#### Scenario: inspect setup output
- **WHEN** setup completes
- **THEN** a schema-valid setup report is written or returned
