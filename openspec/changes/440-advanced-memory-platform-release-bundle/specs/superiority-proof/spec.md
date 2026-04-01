# superiority-proof/spec.md

## Requirements

### Requirement: advanced-runtime report
OpenDream MUST generate a advanced-runtime report that combines execution-surface evidence with memory-excellence evidence.

#### Scenario: release-check
- **WHEN** release-check runs
- **THEN** it emits a schema-valid advanced-runtime report

### Requirement: supported modes stay within excellence budgets
Every supported execution mode MUST preserve the configured memory-excellence budgets.

#### Scenario: one delegated mode regresses
- **WHEN** a delegated execution mode breaches scorecard thresholds
- **THEN** release verification fails
