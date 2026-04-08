# workspace-catalog/spec.md

## Requirements

### Requirement: machine-local derived catalog
OpenDream MUST maintain a machine-local workspace catalog as derived state.

#### Scenario: initialize a workspace
- **WHEN** an operator initializes or activates a workspace
- **THEN** OpenDream can add or update a catalog entry for that workspace
- **AND** the catalog entry does not become canonical over the workspace-local state

### Requirement: stale/missing handling
OpenDream MUST preserve stale or missing entries diagnostically rather than deleting them silently.

#### Scenario: workspace path missing
- **WHEN** a known workspace path no longer exists
- **THEN** the catalog marks it missing or stale
- **AND** surfaces remediation

### Requirement: sandbox guard on event-driven writes
OpenDream MUST NOT touch the real machine home catalog from event-driven hooks when the process is running under a test runner or when the target workspace resides under a tempdir, unless the operator has explicitly opted in by setting `OPENDREAM_CATALOG_HOME` or supplying an explicit home argument.

#### Scenario: init under a tempdir without opt-in
- **WHEN** `opendream init` runs against a workspace whose resolved path is under a system tempdir
- **AND** `OPENDREAM_CATALOG_HOME` is not set
- **THEN** the `catalog_update` block on the command result reports `status: "skipped"` with `reason: "tempdir-workspace"`
- **AND** the real `~/.opendream/catalog.json` is not modified

#### Scenario: init under a pytest/unittest runner without opt-in
- **WHEN** any command that performs a catalog write runs under a detected test runner
- **AND** `OPENDREAM_CATALOG_HOME` is not set
- **THEN** the write is skipped with `reason: "sandboxed-environment"` and the real home catalog is not modified

#### Scenario: operator opts in via OPENDREAM_CATALOG_HOME
- **WHEN** `OPENDREAM_CATALOG_HOME` is set to an explicit location
- **THEN** event-driven writes proceed against that location and are not silently skipped
