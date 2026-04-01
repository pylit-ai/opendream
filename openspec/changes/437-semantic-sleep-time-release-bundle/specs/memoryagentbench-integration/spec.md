# memoryagentbench-integration/spec.md

## Requirements

### Requirement: AR/TTL/LRU/CR measurement
OpenDream MUST expose benchmark surfaces for Accurate Retrieval, Test-Time Learning, Long-Range Understanding, and Conflict Resolution style measurements.

#### Scenario: run MAB-style eval
- **WHEN** an operator runs `opendream eval memory-agent-bench`
- **THEN** scores are emitted for each competency plus an aggregate score

### Requirement: clean-room adapter policy
OpenDream MUST be able to run benchmark adapters without requiring redistribution of unlicensed third-party benchmark code.

#### Scenario: no vendored benchmark code
- **WHEN** redistribution rights are absent or unconfirmed
- **THEN** OpenDream uses clean-room adapters and user-supplied local benchmark inputs
