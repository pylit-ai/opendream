## ADDED Requirements

### Requirement: Semantic-First Workspace Posture
OpenDream MUST treat semantic-first as the default posture for new and repaired workspaces while distinguishing posture from actual semantic readiness.

#### Scenario: Ready semantic workspace
- **WHEN** the operator initializes or repairs a workspace and a supported semantic execution path plus return path are available
- **THEN** status and machine-readable outputs identify the workspace as semantic-ready and report the active execution strategy

#### Scenario: Degraded semantic-first workspace
- **WHEN** the operator initializes or repairs a workspace and no supported semantic execution path is currently runnable
- **THEN** status and machine-readable outputs identify the workspace as degraded, explain the degraded reason, and recommend one next action

#### Scenario: Deterministic by explicit choice
- **WHEN** the operator explicitly disables semantic-first posture for a workspace
- **THEN** status and machine-readable outputs identify the workspace as deterministic-by-choice rather than degraded

### Requirement: Truthful Semantic Status
OpenDream MUST NOT label a workspace semantic-ready solely because semantic mode was configured in a file.

#### Scenario: Configured mode without runnable execution
- **WHEN** semantic mode is configured but no provider or delegated adapter is available
- **THEN** every primary status surface reports that semantic capability is unavailable or degraded instead of claiming readiness
