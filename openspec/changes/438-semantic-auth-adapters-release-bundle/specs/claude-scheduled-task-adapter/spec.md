# claude-scheduled-task-adapter/spec.md

## Requirements

### Requirement: Claude scheduled-task delegated semantic execution
OpenDream MUST support a Claude adapter that runs semantic refresh through Claude scheduled tasks rather than direct OpenDream-owned provider calls.

#### Scenario: desktop task path
- **WHEN** Claude Code is configured locally and local files are needed
- **THEN** OpenDream can scaffold a Desktop-task-compatible command/skill/prompt path
- **AND** outputs return through delegated ingest

#### Scenario: cloud task path
- **WHEN** Claude Cloud scheduling is preferred
- **THEN** OpenDream can scaffold a cloud-safe task template that avoids undocumented local-file assumptions

### Requirement: no false direct-auth claim
OpenDream MUST NOT describe Claude delegated mode as OpenDream directly reusing Claude auth.

#### Scenario: status or docs
- **WHEN** an operator inspects status/docs
- **THEN** the owner of execution is shown as Claude delegated runtime
