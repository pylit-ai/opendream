## ADDED Requirements

### Requirement: Migration hints for older surfaces
Older service or autowire entrypoints MUST remain functional for a migration window and point operators toward the compressed primary commands.

#### Scenario: Older command returns a migration hint
- **GIVEN** an operator uses an older service or autowire surface
- **WHEN** OpenDream completes that command successfully
- **THEN** the output includes a hint toward the compressed primary commands
