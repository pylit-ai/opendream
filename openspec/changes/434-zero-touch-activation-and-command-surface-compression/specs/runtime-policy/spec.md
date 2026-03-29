## ADDED Requirements

### Requirement: Event-driven default runtime policy
The standard path MUST default to event-driven post-task drain and only require background service installation when backlog or replay policy actually needs it.

#### Scenario: Common path avoids daemon mental overhead
- **GIVEN** a normal activated workspace
- **WHEN** the operator follows the standard path
- **THEN** they do not need daemon or cron knowledge to keep the common integration working
