# grep-first-retrieval/spec.md

## Requirements

### Requirement: probe-first transcript access
Transcript gathering MUST start with targeted probes before bounded reads.

#### Scenario: dream gather phase
- **WHEN** the gather phase runs
- **THEN** it executes probe operations first
- **AND** reads bounded windows only around probe hits or explicit escalations

### Requirement: no default full-corpus replay
Whole-corpus transcript replay MUST remain disabled by default.

#### Scenario: run default dream mode
- **WHEN** a normal dream run occurs
- **THEN** the worker does not bulk-load the entire transcript corpus
