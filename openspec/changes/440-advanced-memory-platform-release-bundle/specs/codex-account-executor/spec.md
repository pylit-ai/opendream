# codex-account-executor/spec.md

## Requirements

### Requirement: trusted Codex execution
OpenDream MUST support a Codex-backed semantic adapter for trusted local/private contexts.

#### Scenario: trusted local machine
- **WHEN** Codex is installed and account-backed auth is available
- **THEN** setup can recommend `codex-account`
- **AND** scaffolding and status surfaces are available

### Requirement: trust-boundary enforcement
OpenDream MUST NOT recommend Codex account-backed mode in unsupported trust contexts.

#### Scenario: public or untrusted runner
- **WHEN** setup detects such a context
- **THEN** `codex-account` is blocked or downgraded with explicit remediation
