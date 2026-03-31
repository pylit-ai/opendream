## ADDED Requirements

### Requirement: Spec registry reconciliation

All entries in `specs/registry.yaml` SHALL have a `status` field that accurately reflects the current implementation state. No spec SHALL claim `active` status when its implementation is complete (should be `implemented`) or when it has been replaced (should be `superseded`).

#### Scenario: Registry status matches implementation reality

- **WHEN** `specs/registry.yaml` is inspected
- **THEN** every entry with status `implemented` has all acceptance criteria met in code
- **AND** every entry with status `superseded` references its replacement
- **AND** no entry claims `active` when the corresponding code is complete and tested

### Requirement: Clean verification evidence

The release process SHALL produce verification artifacts from a clean environment. At minimum, `make verify` SHALL produce `.tmp/verification/verification_report.json` and `make release-check` SHALL produce `.tmp/release-check/release_manifest.json` and `.tmp/release-check/release_summary.md`.

#### Scenario: Verification artifacts are complete

- **WHEN** `make release-check` completes
- **THEN** all three artifact files exist, contain valid JSON/markdown, and the manifest includes git SHA, platform, and artifact hashes

### Requirement: Extended eval corpus

An extended performance evaluation fixture SHALL exist at `opendream/fixtures/performance_eval_extended.json` covering task archetypes beyond the base fixture: environment gotchas, multi-step conflicting decisions, high-noise sessions, and cross-temporal contradiction patterns.

#### Scenario: Extended fixture adds task diversity

- **WHEN** the extended fixture is loaded
- **THEN** it contains at least 3 additional high-signal event types and 2 additional gating query patterns not present in the base fixture
