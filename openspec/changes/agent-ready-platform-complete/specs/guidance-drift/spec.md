# guidance-drift/spec.md

## ADDED Requirements

### Requirement: friction clustering
OpenDream MUST cluster repeated friction signals into reviewable guidance-drift proposals.

#### Scenario: repeated user correction
- **WHEN** similar corrections or verification failures recur across sessions
- **THEN** OpenDream emits a proposal record describing the repeated issue, suggested target surface, and supporting evidence

### Requirement: proposal-only default
OpenDream MUST treat guidance-drift outputs as proposals until explicitly promoted.

#### Scenario: guidance-drift run completes
- **WHEN** a guidance-drift engine writes outputs
- **THEN** the outputs remain in the automation projection layer
- **AND** canonical docs remain unchanged until promotion

### Requirement: promotion path
OpenDream MUST provide a path to promote accepted proposals into canonical docs, skills, or proposal bundles.

#### Scenario: accept a proposal
- **WHEN** an operator promotes an accepted guidance-drift proposal
- **THEN** OpenDream writes the target artifact or an OpenSpec change bundle
- **AND** records provenance linking the new artifact to the proposal evidence
