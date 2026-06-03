# ADR-010: Benchmark suite and harness optimization

## Status
Accepted

## Context
The semantic sleep-time release must demonstrate that semantic mode improves utility without harmful side effects. Release evidence requires multiple evaluation tiers: cheap regression tests for CI, competency benchmarks for capability tracking, and realistic task evaluations for end-to-end validation. Additionally, benchmark harness configuration (prompt templates, retrieval parameters, scoring weights) should be optimizable to find effective operating points.

## Decision
Introduce a unified benchmark suite with:

1. **Controlled fixtures** — lightweight regression tests using `tests/fixtures/` corpora, runnable in CI with no external dependencies.
2. **MemoryAgentBench-style adapters** — clean-room adapters that implement the MemoryAgentBench evaluation protocol without vendoring unlicensed code (see ADR-011).
3. **Coding-task evaluations** — task-based evals measuring retrieval-augmented code generation quality.
4. **Harness optimization** — automated parameter sweeps over retrieval weights, context budgets, and prompt templates with result tracking.

Benchmark commands are exposed via `opendream benchmark run`, `opendream benchmark report`, and `opendream benchmark optimize`. Release gates require passing thresholds on regression tests and competency benchmarks before a release is tagged.

## Consequences
- New `opendream.benchmark` module with fixture-based, adapter-based, and task-based eval runners
- New CLI commands for benchmark execution, reporting, and optimization
- Release gates tied to benchmark pass/fail; blocks release on regression
- Clean-room adapter policy (ADR-011) governs third-party benchmark integration
- Harness optimization produces parameter configurations stored under `benchmarks/configs/`

## Alternatives considered
- Manual evaluation only (rejected: not reproducible, does not scale)
- Single benchmark tier (rejected: conflates fast regression checks with expensive end-to-end evals)
- Vendor third-party benchmark code directly (rejected: licensing concerns per ADR-011)

## References
- ADR-011: Third-party provenance and reuse policy
- MemoryAgentBench (Tian et al., 2025)
- Sleep-time Compute paper (Luo et al., 2025)
