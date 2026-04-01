# benchmark-suite/spec.md

## Requirements

### Requirement: benchmark modes
The benchmark suite MUST run deterministic-only, semantic-only, and hybrid modes.

#### Scenario: benchmark invocation
- **WHEN** an operator runs the benchmark suite
- **THEN** comparative scorecards are emitted across all supported modes

### Requirement: memory-hurt accounting
Benchmarks MUST measure memory-hurt explicitly.

#### Scenario: harmful memory use
- **WHEN** stale or contradicted memory degrades performance
- **THEN** the benchmark report classifies the harm source and impact
