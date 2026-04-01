# procedural-memory/spec.md

## Requirements

### Requirement: richer procedural memory
Procedural memory MUST capture workflow steps plus preconditions, recovery steps, and anti-patterns.

#### Scenario: workflow extracted
- **WHEN** a procedural workflow is extracted
- **THEN** the stored memory includes actionable reuse structure, not only a summary sentence

### Requirement: procedural-aware retrieval
Procedural memory MUST be preferentially considered for task-shaped queries.

#### Scenario: repeated task
- **WHEN** a user asks how to perform a repeated workflow
- **THEN** relevant procedural memory is ranked and explained ahead of generic note-like context
