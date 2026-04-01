# codex-auth-adapter/spec.md

## Requirements

### Requirement: trusted Codex account-backed semantic execution
OpenDream MUST support a Codex-backed semantic adapter that uses Codex-managed account authentication on trusted local/private infrastructure.

#### Scenario: trusted local machine
- **WHEN** Codex is installed and account-backed auth is available
- **THEN** OpenDream can scaffold and validate a Codex semantic adapter
- **AND** semantic runs can be owned by Codex rather than a direct provider client

### Requirement: trust-boundary enforcement
OpenDream MUST warn or reject when Codex account-backed mode is configured for unsupported trust contexts.

#### Scenario: public CI or untrusted runner
- **WHEN** setup detects an untrusted/public automation context
- **THEN** OpenDream does not recommend Codex account-backed mode
- **AND** recommends direct-provider or deterministic fallback instead
