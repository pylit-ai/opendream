# claude-scheduled-executor/spec.md

## Requirements

### Requirement: Claude delegated scheduled execution
OpenDream MUST support a Claude adapter that runs semantic work through Claude scheduling surfaces and returns structured results to OpenDream.

#### Scenario: desktop schedule
- **WHEN** a local repo and local tools are needed
- **THEN** a desktop-compatible scaffold is generated

#### Scenario: cloud schedule
- **WHEN** durable cloud scheduling is preferred
- **THEN** a cloud-safe scaffold is generated

### Requirement: delegated ownership
OpenDream MUST represent Claude mode as delegated execution.

#### Scenario: inspect status/docs
- **WHEN** an operator inspects the mode
- **THEN** ownership is shown as Claude delegated runtime, not direct OpenDream provider execution
