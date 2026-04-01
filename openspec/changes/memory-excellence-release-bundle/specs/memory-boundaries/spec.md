# memory-boundaries/spec.md

## Requirements

### Requirement: enforced memory-only maintenance
Dream and semantic workers MUST be runtime-constrained to memory-only writes.

#### Scenario: worker attempts code write
- **WHEN** a maintenance worker attempts to write outside the memory/audit allowlist
- **THEN** the write is blocked
- **AND** a boundary-violation artifact is emitted

### Requirement: explicit no-code-write verification
Release verification MUST include a no-code-write check.

#### Scenario: verify run completes
- **WHEN** `make verify` completes
- **THEN** the repo diff shows only allowed memory/audit paths changed by maintenance runs
