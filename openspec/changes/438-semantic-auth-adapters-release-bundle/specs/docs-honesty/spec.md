# docs-honesty/spec.md

## Requirements

### Requirement: semantic docs must describe execution ownership honestly
OpenDream documentation MUST distinguish between direct-provider semantic execution and vendor-delegated semantic execution.

#### Scenario: reading setup docs
- **WHEN** an operator reads the README, FAQ, or semantic setup docs
- **THEN** the docs state whether OpenDream or a vendor runtime owns the model call
- **AND** the docs state whether extra provider keys are required
- **AND** the docs do not imply generic OAuth reuse

### Requirement: release notes must match shipped behavior
Release notes MUST describe semantic support in terms that match implemented and tested execution strategies.

#### Scenario: preparing release notes
- **WHEN** release artifacts are generated
- **THEN** wording checks fail if notes claim unsupported magic or hide required setup
