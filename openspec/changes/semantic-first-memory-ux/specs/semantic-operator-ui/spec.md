## ADDED Requirements

### Requirement: Semantic Readiness UI
OpenDream MUST make semantic readiness, degraded state, and next action visible on the primary observe surfaces.

#### Scenario: Overview for degraded workspace
- **WHEN** the operator opens `/overview` for a degraded semantic-first workspace
- **THEN** the page shows the degraded state, reason, and next action ahead of lower-level raw details

#### Scenario: Settings for ready workspace
- **WHEN** the operator opens `/settings` for a semantic-ready workspace
- **THEN** the page shows the active execution strategy, trust notes, and access to expandable raw configuration

### Requirement: Context Preview UI
OpenDream MUST show how progressive disclosure and pruning affected the assembled context.

#### Scenario: Context preview
- **WHEN** the operator views the semantic readiness and memory-quality surfaces in observe
- **THEN** the UI shows the active context profile, raw candidate count, injected count, and pruning evidence with links to inspectable artifacts

### Requirement: Raw Mode Controls Behind Disclosure
OpenDream MUST NOT make a raw mode selector the primary semantic UI affordance.

#### Scenario: Advanced controls
- **WHEN** an operator needs direct access to underlying mode controls or raw JSON
- **THEN** the UI exposes them behind progressive disclosure without hiding the higher-signal readiness summary
