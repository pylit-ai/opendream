## ADDED Requirements

### Requirement: Compressed primary command surface
The top-level CLI MUST promote init, activate, status, repair, and deactivate as the primary operator path.

#### Scenario: Primary help shows the compressed contract
- **GIVEN** an operator runs `opendream --help`
- **WHEN** the CLI renders top-level help
- **THEN** the compressed primary commands are shown as the normal path
- **AND** advanced surfaces remain available but clearly secondary
