## ADDED Requirements

### Requirement: Benchmark methodology document

A benchmark methodology document SHALL exist at `docs/benchmarks/methodology.md` describing: the evaluation dimensions (write precision, retrieval precision, latency, concurrency safety, contradiction handling, procedural reuse, gating accuracy), weighting formula, pass/fail thresholds, fixture design rationale, and known limitations of fixture-driven evaluation.

#### Scenario: Methodology is self-contained

- **WHEN** a reader opens `docs/benchmarks/methodology.md`
- **THEN** they can understand how the scorecard is computed without reading source code

### Requirement: Skeptical engineer FAQ

A FAQ document SHALL exist at `docs/FAQ.md` covering: what OpenDream is, what problem it solves, how it differs from AutoDream, what it does not do, local-first/privacy posture, current license/distribution terms, known limitations, and benchmark methodology summary.

#### Scenario: FAQ answers common questions

- **WHEN** a technical user reads `docs/FAQ.md`
- **THEN** each listed topic has a concise answer (1-3 sentences) with pointers to detailed docs where applicable

### Requirement: Quickstart path under 5 minutes

The README quickstart section SHALL provide a copy-paste command sequence that takes a new user from zero to a meaningful first success (init → emit → maintain → context) in under 5 minutes on a machine with Python 3.11+ and pip/uv installed.

#### Scenario: Quickstart works on clean install

- **WHEN** a user follows the README quickstart on a machine with Python 3.11+ and uv
- **THEN** they complete init, emit-event, maintain, and prepare-context successfully
- **AND** the total wall-clock time is under 5 minutes including install
