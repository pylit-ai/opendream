# workspace-cli/spec.md

## Requirements

### Requirement: workspace command family
OpenDream MUST expose first-party CLI commands for listing, scanning, inspecting, forgetting, and doctoring workspaces.

#### Scenario: list workspaces
- **WHEN** an operator runs `opendream workspace list`
- **THEN** OpenDream returns all known catalog entries in a bounded, reviewable form

#### Scenario: forget workspace
- **WHEN** an operator runs `opendream workspace forget`
- **THEN** only the catalog entry is removed
- **AND** the workspace-local `.opendream/` state remains untouched
