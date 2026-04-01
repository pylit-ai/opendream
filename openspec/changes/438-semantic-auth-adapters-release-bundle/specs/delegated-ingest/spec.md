# delegated-ingest/spec.md

## Requirements

### Requirement: validated delegated envelopes
OpenDream MUST validate delegated semantic envelopes before ingest.

#### Scenario: valid envelope
- **WHEN** an envelope matches schema
- **THEN** OpenDream ingests it and records provenance, run metadata, and resulting proposals/events

#### Scenario: invalid envelope
- **WHEN** an envelope fails validation
- **THEN** OpenDream rejects it
- **AND** archives the failure with a diagnostic artifact

### Requirement: bounded mutation
Delegated ingest MUST NOT directly mutate canonical durable memory.

#### Scenario: ingest completes
- **WHEN** OpenDream ingests delegated semantic output
- **THEN** the result enters learned-context proposal and/or event pathways
- **AND** normal verification/promotion rules still apply
