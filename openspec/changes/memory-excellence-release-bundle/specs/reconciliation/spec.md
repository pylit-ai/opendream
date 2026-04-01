# reconciliation/spec.md

## Requirements

### Requirement: reconciliation sweep
OpenDream MUST provide a reconciliation sweep for stale and drifted memory artifacts.

#### Scenario: orphaned view or renamed root
- **WHEN** a project root is renamed or a compat view becomes orphaned
- **THEN** the sweep detects the drift and records a bounded repair outcome

### Requirement: provenance-safe repairs
Reconciliation MUST preserve provenance.

#### Scenario: stale record downgraded
- **WHEN** the sweep downgrades or quarantines a stale record
- **THEN** the original provenance remains inspectable
- **AND** the repair reason is recorded
