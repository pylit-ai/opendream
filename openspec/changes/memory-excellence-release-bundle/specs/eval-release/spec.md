# eval-release/spec.md

## Requirements

### Requirement: memory-excellence scorecard
Release verification MUST produce a memory-excellence scorecard.

#### Scenario: release-check runs
- **WHEN** `make release-check` completes
- **THEN** it archives a scorecard covering stale-claim prevention, contradiction resolution, irrelevant recall, derivability hygiene, procedural reuse, concurrency safety, and repeated coding-task improvement

### Requirement: scorecard thresholds block release
Release MUST fail when scorecard thresholds are not met.

#### Scenario: contradiction accuracy regresses
- **WHEN** contradiction resolution accuracy or stale-claim prevention falls below threshold
- **THEN** release verification fails
