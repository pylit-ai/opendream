## ADDED Requirements

### Requirement: Semantic Memory Quality Diagnostics
OpenDream MUST diagnose memory-quality failure modes that make a workspace look semantically healthy when it is not.

#### Scenario: Homogeneous memory warning
- **WHEN** recent durable memory is dominated by a single low-signal type such as generic `semantic_fact`
- **THEN** doctor and machine-readable status surfaces emit a type-diversity warning with remediation guidance

#### Scenario: No learned-context activity
- **WHEN** a semantic-first workspace shows no learned-context activity across the configured observation window
- **THEN** doctor and machine-readable status surfaces warn that semantic value is not currently materializing

#### Scenario: Ephemera-heavy capture
- **WHEN** recent promoted memory contains a high ratio of waiting, running, or similarly ephemeral summaries
- **THEN** doctor and machine-readable status surfaces warn that capture quality or pruning is insufficient

### Requirement: Homogeneous Workspace Regression Fixture
OpenDream MUST maintain a regression fixture for the failure mode where semantic posture is requested but semantic capability is unavailable and durable memory remains flat and homogeneous.

#### Scenario: Fixture evaluation
- **WHEN** the regression suite runs against the homogeneous-memory fixture
- **THEN** the fixture fails healthy-semantic expectations and produces the expected quality warnings
