## ADDED Requirements

### Requirement: Repo-local wrapper fallback
The system MUST provide a repo-local wrapper only for targets whose native lifecycle hooks are insufficient.

#### Scenario: Codex uses a managed wrapper path
- **GIVEN** Codex is configured in the workspace
- **WHEN** activation installs Codex managed surfaces
- **THEN** OpenDream writes a repo-local wrapper and AGENTS guidance
- **AND** the wrapper preserves the wrapped command exit code
