# isolated-execution/spec.md

## ADDED Requirements

### Requirement: isolated execution for code mutation
OpenDream MUST require isolated execution for unattended automation engines whose side-effect class is `code_mutation`.

#### Scenario: run a code-mutating automation
- **WHEN** a code-mutating automation is triggered
- **THEN** OpenDream creates an isolated worktree
- **AND** executes the run there instead of in the primary workspace

### Requirement: primary workspace protection
OpenDream MUST block unattended code mutation in the primary workspace.

#### Scenario: attempt primary workspace mutation
- **WHEN** a code-mutating unattended job lacks isolated mode
- **THEN** OpenDream rejects the run before mutation begins

### Requirement: auditable run artifacts
OpenDream MUST emit worktree-aware reports for isolated runs.

#### Scenario: inspect an isolated run
- **WHEN** an operator inspects the run
- **THEN** OpenDream shows the worktree path, base ref, diff summary, verification status, cleanup status, and any preserved debug paths
