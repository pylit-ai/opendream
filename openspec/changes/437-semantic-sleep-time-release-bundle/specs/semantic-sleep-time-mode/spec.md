# semantic-sleep-time-mode/spec.md

## Requirements

### Requirement: first-class semantic mode
OpenDream MUST implement a model-backed semantic sleep-time mode alongside deterministic mode.

#### Scenario: run semantic mode
- **WHEN** an operator runs `opendream dream run --mode semantic`
- **THEN** OpenDream performs semantic anticipation/synthesis/verification
- **AND** emits a semantic dream report
- **AND** writes proposal artifacts even if promotion is blocked

### Requirement: hybrid mode
OpenDream MUST support a hybrid deterministic + semantic mode.

#### Scenario: run hybrid mode
- **WHEN** an operator runs `opendream dream run --mode hybrid`
- **THEN** durable typed memory and learned-context outputs are both produced under one coordinated run report

### Requirement: explicit fallback
OpenDream MUST make fallback behavior explicit.

#### Scenario: semantic provider unavailable
- **WHEN** semantic mode is requested and provider health checks fail
- **THEN** OpenDream either fails explicitly or falls back according to configured policy
- **AND** the run report states what happened
