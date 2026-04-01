# coding-task-evals/spec.md

## Requirements

### Requirement: repeated coding-task task suite
OpenDream MUST provide repeated coding-task evals that measure practical utility, not just memory recall.

#### Scenario: run coding-task eval
- **WHEN** an operator runs the coding-task eval suite
- **THEN** task success, cost, latency, irrelevant recall, contradiction recovery, and procedural reuse are reported by mode

### Requirement: release use
Coding-task evals MUST contribute to release evidence.

#### Scenario: release check
- **WHEN** `make release-check` runs
- **THEN** coding-task eval results are included or linked in the release manifest
