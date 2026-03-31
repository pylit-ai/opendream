## ADDED Requirements

### Requirement: Documented AutoDream comparison methodology

A comparison document SHALL exist at `docs/benchmarks/autodream-comparison.md` that provides a dimension-by-dimension analysis of OpenDream vs AutoDream. The document SHALL cover: write-path filtering, retrieval strategy, concurrency safety, audit trail, contradiction handling, procedural memory, and performance measurement. Each dimension SHALL include: what AutoDream does (with evidence source), what OpenDream does (with code/test reference), and a verdict.

#### Scenario: Comparison document exists and covers all dimensions

- **WHEN** a reader opens `docs/benchmarks/autodream-comparison.md`
- **THEN** the document contains sections for each of the seven comparison dimensions with evidence-backed claims

#### Scenario: Each claim references verifiable evidence

- **WHEN** a claim is made about AutoDream capability
- **THEN** the claim includes a citation to official docs, GitHub issues, or public analysis with URL
- **WHEN** a claim is made about OpenDream capability
- **THEN** the claim references a specific code path, test, or eval result

### Requirement: Honest limitations section

The comparison document SHALL include a section documenting known limitations, negative results, and areas where OpenDream has not yet proven superiority. This section SHALL include at least: scenarios where memory retrieval hurts performance, limitations of fixture-driven evaluation, and areas requiring further measurement.

#### Scenario: Limitations are specific and actionable

- **WHEN** a reader reviews the limitations section
- **THEN** each limitation describes the specific gap, why it matters, and what would close it

### Requirement: Reproduction instructions

The comparison document SHALL include instructions for reproducing OpenDream's benchmark results locally using `make verify` and `opendream eval performance`.

#### Scenario: Reproduction path works

- **WHEN** a user follows the reproduction instructions on a clean checkout
- **THEN** they can run the performance eval and obtain a scorecard matching the documented methodology
