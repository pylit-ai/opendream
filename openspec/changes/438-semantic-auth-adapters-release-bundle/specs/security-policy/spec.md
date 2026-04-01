# security-policy/spec.md

## Requirements

### Requirement: unsupported OAuth reuse is never recommended
OpenDream MUST reject or explicitly mark unsupported third-party OAuth reuse paths as unsupported.

#### Scenario: Gemini detected
- **WHEN** setup detects Gemini tooling
- **THEN** OpenDream does not recommend Gemini OAuth reuse
- **AND** explains why

### Requirement: sensitive auth caches are handled as secrets
OpenDream MUST treat vendor auth caches used by supported adapters as sensitive.

#### Scenario: Codex auth cache present
- **WHEN** status/setup reports on Codex account-backed mode
- **THEN** reports redact sensitive material
- **AND** docs warn against logging/committing the auth cache
