# execution-surface-policy/spec.md

## Requirements

### Requirement: explicit execution ownership
OpenDream MUST make semantic execution ownership explicit.

#### Scenario: inspect status
- **WHEN** an operator runs semantic or dream status
- **THEN** the output shows whether execution is owned by OpenDream, Codex, Claude, Cursor, or deterministic fallback

### Requirement: no ambiguous docs
Docs MUST use the same ownership vocabulary as the runtime.

#### Scenario: read setup docs
- **WHEN** an operator reads semantic setup documentation
- **THEN** the docs distinguish direct-provider and delegated execution precisely
