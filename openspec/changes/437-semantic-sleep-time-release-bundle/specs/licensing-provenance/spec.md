# licensing-provenance/spec.md

## Requirements

### Requirement: explicit provenance inventory
OpenDream MUST record provenance for any copied or vendored third-party code or prompts used in semantic mode.

#### Scenario: inspect third-party notices
- **WHEN** an operator reviews release evidence
- **THEN** each third-party artifact lists source, license, path, and rationale

### Requirement: no unlicensed vendoring
OpenDream MUST NOT vendor benchmark or harness-optimizer code without a confirmed redistribution right.

#### Scenario: unconfirmed license
- **WHEN** a third-party archive lacks a clear redistributable license grant
- **THEN** OpenDream uses clean-room adapters or reference-only integration instead
