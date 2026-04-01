# anticipation-planner/spec.md

## Requirements

### Requirement: query-family inference
OpenDream MUST infer likely future query families from recent activity or configured manifests.

#### Scenario: repeated task archetypes observed
- **WHEN** similar task/retrieval patterns recur
- **THEN** OpenDream emits query-family tags and uses them to target semantic synthesis

### Requirement: budget-aware selection
OpenDream MUST select query families under configurable budgets.

#### Scenario: too many possible families
- **WHEN** the raw family set exceeds the budget
- **THEN** OpenDream ranks and truncates the set deterministically or according to configured policy
