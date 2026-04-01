# delegated-ingest/spec.md

## Requirements

### Requirement: validated delegated envelopes
OpenDream MUST validate all delegated semantic envelopes before ingest.

#### Scenario: valid envelope
- **WHEN** a valid envelope is present
- **THEN** OpenDream converts it into proposals and/or events with provenance

#### Scenario: invalid envelope
- **WHEN** validation fails
- **THEN** OpenDream rejects and archives it with diagnostics

### Requirement: bounded mutation
Delegated ingest MUST NOT directly overwrite canonical durable truth.

#### Scenario: ingest completes
- **WHEN** delegated semantic output is accepted
- **THEN** normal verification/promotion pathways still apply
