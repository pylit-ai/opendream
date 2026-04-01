# docs-honesty/spec.md

## Requirements

### Requirement: truthful operator docs
OpenDream docs MUST say when extra provider keys are or are not required.

#### Scenario: read FAQ / README
- **WHEN** an operator asks how semantic mode runs
- **THEN** docs provide an explicit matrix by execution mode

### Requirement: no unsupported shortcuts
OpenDream docs MUST NOT recommend unsupported OAuth piggybacking.

#### Scenario: unsupported path appears in docs
- **WHEN** wording checks run
- **THEN** release verification fails
