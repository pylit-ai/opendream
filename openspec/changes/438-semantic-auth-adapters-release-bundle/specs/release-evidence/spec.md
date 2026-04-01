# release-evidence/spec.md

## Requirements

### Requirement: release wording gate
Release verification MUST include a wording gate that fails when docs or notes imply unsupported semantic behavior.

#### Scenario: forbidden wording present
- **WHEN** a release artifact claims generic OAuth reuse or hides required setup
- **THEN** release verification fails

### Requirement: adapter evidence
Release verification MUST produce evidence that setup and adapter scaffolds are real.

#### Scenario: release-check completes
- **WHEN** release-check runs
- **THEN** it includes adapter detection results, scaffold smoke results, and doc honesty results
