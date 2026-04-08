# workspace-docs/spec.md

## Requirements

### Requirement: docs explain both models
Docs MUST explain:
1. current workspace-scoped state
2. the new machine-local catalog

#### Scenario: read README or FAQ
- **WHEN** an operator reads docs for this feature
- **THEN** they understand that the catalog is a convenience index, not canonical truth

### Requirement: dashboard discoverability
Docs MUST point operators to the dashboard route and workspace commands.

#### Scenario: search for workspace dashboard
- **WHEN** an operator reads the docs
- **THEN** the route and CLI commands are easy to find
