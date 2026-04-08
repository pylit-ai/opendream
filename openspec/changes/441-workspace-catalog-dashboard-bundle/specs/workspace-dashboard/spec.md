# workspace-dashboard/spec.md

## Requirements

### Requirement: dashboard route
OpenDream MUST provide a UI route listing all known workspaces.

#### Scenario: open dashboard
- **WHEN** an operator opens `/workspaces`
- **THEN** OpenDream shows a summary and per-workspace cards or rows

### Requirement: central navigation
The workspace dashboard MUST provide a central place to navigate into specific workspace views.

#### Scenario: open workspace from dashboard
- **WHEN** an operator clicks a workspace card
- **THEN** OpenDream navigates into the existing workspace view or equivalent detail page
