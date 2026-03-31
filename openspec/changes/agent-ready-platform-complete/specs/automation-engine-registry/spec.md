# automation-engine-registry/spec.md

## ADDED Requirements

### Requirement: declared engine resolution
OpenDream MUST resolve unattended automation execution through a declared engine registry.

#### Scenario: register a job with a built-in engine
- **WHEN** an operator registers a job using a built-in engine id
- **THEN** OpenDream validates the engine contract and job compatibility before acceptance

#### Scenario: register a job with an unknown engine
- **WHEN** an operator references an unknown engine id
- **THEN** OpenDream rejects the job
- **AND** no unattended execution path is created

### Requirement: engine contracts
OpenDream MUST require engine manifests to declare side-effect class, input contract, output schema, and review policy.

#### Scenario: inspect an engine
- **WHEN** an operator inspects a registered engine
- **THEN** OpenDream returns its manifest, execution policy, and supported selectors

### Requirement: no arbitrary unattended shell execution
OpenDream MUST NOT use undeclared shell commands or arbitrary `SKILL.md` execution as the unattended automation model.

#### Scenario: attempt to schedule an ad hoc shell task
- **WHEN** a user attempts to register an unattended shell-only automation with no engine contract
- **THEN** OpenDream rejects the registration
- **AND** points to the engine registry path
