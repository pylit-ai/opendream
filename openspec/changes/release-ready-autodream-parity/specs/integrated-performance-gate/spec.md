## ADDED Requirements

### Requirement: Performance eval runs as part of make verify

The verification pipeline (`scripts/verify.py`) SHALL include `eval performance` as a named stage that runs in a hermetic temp workspace. The stage SHALL fail the overall verification if the performance scorecard `weighted_total` is below 80 or if `write_precision` or `retrieval_precision` are below 60.

#### Scenario: Verify includes performance eval and passes

- **WHEN** `make verify` is run on a codebase where performance fixtures produce a passing scorecard
- **THEN** the verification report includes a stage named `performance-eval` with status `PASS` and the overall verdict is `PASS`

#### Scenario: Verify fails when performance threshold not met

- **WHEN** `make verify` is run and the performance scorecard `weighted_total` is below 80
- **THEN** the `performance-eval` stage status is `FAIL` and the overall verification verdict is `FAIL`

### Requirement: Release check archives performance scorecard

The release check (`scripts/release_check.py`) SHALL run `eval performance` in the clean-venv environment and include the full scorecard JSON in the release manifest under a `performance_scorecard` key.

#### Scenario: Release manifest includes scorecard

- **WHEN** `make release-check` completes successfully
- **THEN** `release_manifest.json` contains a `performance_scorecard` key with `weighted_total`, `write_precision`, `retrieval_precision`, `latency`, `concurrency_safety`, `contradiction_handling`, `procedural_reuse`, and `gating_accuracy` fields

#### Scenario: Release check fails on scorecard failure

- **WHEN** `make release-check` runs and the performance eval reports `status: failed`
- **THEN** the corresponding stage in the release manifest has status `FAIL` and the overall verdict is `FAIL`

## MODIFIED Requirements

### Requirement: Verification report structure

The verification report at `.tmp/verification/verification_report.json` SHALL include all existing stages plus a `performance-eval` stage. The stage order SHALL be: lint, typecheck, tests, dream-fidelity-eval, performance-eval, adapters-check, packaging-smoke, lint-probe, typecheck-probe.

#### Scenario: All stages present in report

- **WHEN** `make verify` completes
- **THEN** the report JSON `stages` array contains entries with stage names matching the defined order
