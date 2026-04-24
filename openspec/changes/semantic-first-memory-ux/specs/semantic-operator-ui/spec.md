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

### Requirement: Semantic Change Review UI
OpenDream MUST separate summary-first semantic change review on `/overview` from the detailed compare surface on `/semantic-changes`.

#### Scenario: Overview summarizes semantic changes without pretending to be a diff
- **WHEN** the operator opens `/overview` after OpenDream has recorded a comparable learned-context change set
- **THEN** the page shows summary cards for kept active, suppressed in this context, removed from active learned context, and restorable now, with a primary path to review the change set in detail

#### Scenario: Compare page distinguishes suppression from deactivation
- **WHEN** the operator opens `/semantic-changes` for the latest comparable learned-context change set
- **THEN** the page shows a compare surface with filters, structured before/after state, explicit suppression vs removal labels, and view modes that do not rely on color alone

#### Scenario: Operator restores a recent learned-context record from compare review
- **WHEN** the operator restores a recent learned-context record from `/semantic-changes` while it remains inside the restore window
- **THEN** OpenDream reactivates the record through an explicit UI action, refreshes the semantic change review state, and does not silently imply that unrelated suppression rules changed

### Requirement: Raw Mode Controls Behind Disclosure
OpenDream MUST NOT make a raw mode selector the primary semantic UI affordance.

#### Scenario: Advanced controls
- **WHEN** an operator needs direct access to underlying mode controls or raw JSON
- **THEN** the UI exposes them behind progressive disclosure without hiding the higher-signal readiness summary
