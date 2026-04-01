# feature-mining-runtime/spec.md

## Requirements

### Requirement: adapter-aware feature mining
OpenDream MUST support feature/fix/bug mining and semantic refresh scaffolds across supported execution surfaces.

#### Scenario: scaffold delegated feature mining
- **WHEN** an operator requests a feature-radar or semantic-refresh scaffold for Claude or Cursor
- **THEN** OpenDream generates a runnable delegated pattern with inbox/ingest support

### Requirement: projection truthfulness
Deterministic radar/projection outputs MUST remain non-canonical regardless of execution surface.

#### Scenario: semantic refresh follows radar
- **WHEN** a delegated semantic job processes radar outputs
- **THEN** projections remain labeled as projections until promoted through canonical paths
