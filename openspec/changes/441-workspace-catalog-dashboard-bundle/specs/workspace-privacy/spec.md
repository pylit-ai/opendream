# workspace-privacy/spec.md

## Requirements

### Requirement: no hidden broad scans
OpenDream MUST NOT silently scan arbitrary broad filesystem roots by default.

#### Scenario: fresh install
- **WHEN** the feature is first available
- **THEN** there is no implicit scan of the user home directory

### Requirement: no hidden remote state
OpenDream MUST keep the catalog machine-local and inspectable.

#### Scenario: inspect catalog files
- **WHEN** an operator inspects the catalog
- **THEN** the files are local and human-auditable
