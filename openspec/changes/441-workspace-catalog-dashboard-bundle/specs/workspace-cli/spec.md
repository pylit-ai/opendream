# workspace-cli/spec.md

## Requirements

### Requirement: workspace command family
OpenDream MUST expose first-party CLI commands for listing, scanning, inspecting, forgetting, and doctoring workspaces.

#### Scenario: list workspaces (default human output)
- **WHEN** an operator runs `opendream workspace list` without `--format`
- **THEN** OpenDream prints a human-readable table (status, workspace path, activation summary, service summary)
- **AND** an empty catalog renders an actionable empty-state hint

#### Scenario: list workspaces (machine-readable output)
- **WHEN** an operator runs `opendream workspace list --format json`
- **THEN** OpenDream returns all known catalog entries as JSON suitable for scripts and agents

#### Scenario: forget workspace
- **WHEN** an operator runs `opendream workspace forget`
- **THEN** only the catalog entry is removed
- **AND** the workspace-local `.opendream/` state remains untouched
