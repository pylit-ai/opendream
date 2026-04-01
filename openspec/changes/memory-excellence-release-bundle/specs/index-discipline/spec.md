# index-discipline/spec.md

## Requirements

### Requirement: generated-only compat views
Compatibility views MUST be generated from canonical durable state.

#### Scenario: inspect MEMORY.md
- **WHEN** an operator inspects `MEMORY.md`
- **THEN** it is derivable from canonical state
- **AND** it is not the source of truth

### Requirement: pointer-like startup index
The startup index MUST remain compact and pointer-oriented.

#### Scenario: index generation
- **WHEN** the startup index is regenerated
- **THEN** entries stay within configured budgets
- **AND** each entry resolves to a durable record or topic identifier
