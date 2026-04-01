# meta-harness-optimization/spec.md

## Requirements

### Requirement: environment bootstrap
OpenDream MUST support an environment bootstrap context package for coding-agent harnesses.

#### Scenario: bootstrap enabled
- **WHEN** the bootstrap feature is enabled
- **THEN** initial prompt/context includes repo and runtime snapshot information

### Requirement: harness optimization surface
OpenDream MUST support offline harness optimization runs as a first-class capability.

#### Scenario: optimization smoke run
- **WHEN** an operator runs the harness optimizer on a toy search space
- **THEN** schema-valid reports are emitted with evaluated variants and selected winner

### Requirement: safety
Harness optimization MUST not silently mutate canonical docs, code, or memory state.

#### Scenario: optimization run completes
- **WHEN** the optimization loop finishes
- **THEN** results remain in reports/proposals until explicitly promoted
