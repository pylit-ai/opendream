## ADDED Requirements

### Requirement: Progressive Context Profiles
OpenDream MUST assemble prompt context through explicit profiles that keep startup memory compact and expand only when stronger relevance justifies additional context.

#### Scenario: Startup profile
- **WHEN** the operator or an agent requests startup context without a strong task-specific query
- **THEN** the system returns a pointer-like context profile that prioritizes high-salience typed memory and avoids expanded transcript-like output

#### Scenario: Semantic task profile
- **WHEN** the operator or an agent requests task context with strong semantic relevance
- **THEN** the system returns a bounded expansion that may include learned context and procedural memory under explicit profile budgets

### Requirement: Inspectable Pruning Metadata
OpenDream MUST report what was selected, what was suppressed, and how much prompt budget was saved by pruning.

#### Scenario: Context selection report
- **WHEN** `prepare-context` or an equivalent JSON surface returns assembled prompt context
- **THEN** the response includes the active profile, raw candidate counts, injected counts, suppression reasons, and token or character budget metadata

#### Scenario: Learned-context suppression
- **WHEN** learned context is stale, contradictory, or weakly matched
- **THEN** the selection report explains that the learned context was penalized or suppressed instead of silently omitting it
