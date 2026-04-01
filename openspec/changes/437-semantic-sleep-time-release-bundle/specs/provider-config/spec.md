# provider-config/spec.md

## Requirements

### Requirement: provider registry
OpenDream MUST implement a provider/model registry for semantic mode.

#### Scenario: inspect semantic config
- **WHEN** an operator inspects the semantic configuration
- **THEN** provider id, model roles, budgets, and health are visible

### Requirement: structured-output compatibility
Semantic mode MUST use schema-valid structured outputs or explicit parse-validation paths.

#### Scenario: synthesizer returns malformed output
- **WHEN** structured output parsing fails
- **THEN** the run fails or downgrades according to policy
- **AND** the error is visible in the audit artifact
