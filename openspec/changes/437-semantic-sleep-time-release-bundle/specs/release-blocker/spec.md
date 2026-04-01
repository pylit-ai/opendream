# release-blocker/spec.md

## Requirements

### Requirement: semantic release gate
OpenDream release verification MUST fail if semantic mode is absent, unsafe, or unproven.

#### Scenario: semantic thresholds not met
- **WHEN** hybrid mode underperforms required release thresholds
- **THEN** `make verify` or `make release-check` fails

### Requirement: truthful documentation
Release docs MUST describe semantic mode accurately.

#### Scenario: docs still claim no model-backed consolidation
- **WHEN** release docs are checked
- **THEN** this mismatch fails the release gate
