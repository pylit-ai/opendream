# plugin-distribution/spec.md

## ADDED Requirements

### Requirement: installable thin packages
OpenDream MUST generate installable thin packages for supported agent ecosystems from canonical repository inputs.

#### Scenario: build a Codex package
- **WHEN** an operator builds a Codex package
- **THEN** OpenDream emits a valid plugin structure and manifest
- **AND** the package references canonical docs instead of redefining policy

#### Scenario: build a Claude Code package
- **WHEN** an operator builds a Claude Code package
- **THEN** OpenDream emits a valid plugin with skills, hooks, and marketplace metadata
- **AND** the package can be validated by OpenDream before distribution

#### Scenario: build a Cursor package
- **WHEN** an operator builds a Cursor package
- **THEN** OpenDream emits a valid plugin structure including rules, skills, hooks, and metadata
- **AND** the package remains derived from canonical repo state

#### Scenario: build a GitHub Copilot package
- **WHEN** an operator builds a Copilot package
- **THEN** OpenDream emits repository-wide and path-scoped instruction files
- **AND** the outputs are derived from canonical guidance rather than hand-maintained duplicates

### Requirement: reproducible package reports
OpenDream MUST emit machine-readable reports for package generation and validation.

#### Scenario: inspect a package build
- **WHEN** a package build completes
- **THEN** OpenDream writes a report containing package id, target, schema versions, source hash, and generated files
