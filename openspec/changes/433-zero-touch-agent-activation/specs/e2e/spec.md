## ADDED Requirements

### Requirement: End-to-end activation verification
The system MUST include target-specific activation fixtures in release verification.

#### Scenario: Supported targets prove hook behavior
- **GIVEN** fixture workspaces for Claude Code, Codex, and OpenClaw
- **WHEN** release verification runs
- **THEN** each supported target proves pre-task context injection and post-task runtime capture
- **AND** the release fails if a supported configured target still needs manual glue
