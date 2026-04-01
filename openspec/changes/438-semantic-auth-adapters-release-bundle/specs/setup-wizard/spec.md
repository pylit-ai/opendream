# setup-wizard/spec.md

## Requirements

### Requirement: explicit semantic setup recommendation
OpenDream MUST provide a setup wizard that recommends one supported semantic strategy based on the workspace and operator preference.

#### Scenario: prefer no-extra-key
- **WHEN** an operator runs `opendream semantic setup --prefer no-extra-key`
- **THEN** OpenDream recommends the strongest supported no-extra-key path
- **AND** explains why other paths were not selected

### Requirement: machine-readable setup report
The setup wizard MUST emit a machine-readable report.

#### Scenario: inspect setup output
- **WHEN** setup completes
- **THEN** a setup report includes detected tools, candidate strategies, selected strategy, blockers, and remediation hints
