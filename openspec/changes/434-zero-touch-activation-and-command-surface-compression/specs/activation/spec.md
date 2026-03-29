## ADDED Requirements

### Requirement: Compressed activation path
Activation MUST remain the canonical target detection and managed-surface entrypoint.

#### Scenario: Standard initialization activates configured targets
- **GIVEN** a workspace contains supported configured targets
- **WHEN** the operator runs `opendream init --activate-configured`
- **THEN** OpenDream initializes the memory layout and activates those targets
- **AND** the operator does not need to copy `.meta/` scripts manually
