# Benchmark Methodology

## Overview

OpenDream's performance benchmark is a fixture-driven composite evaluation that scores the memory subsystem across eight dimensions. It runs as part of the standard verification pipeline (`make verify`) and produces a machine-readable scorecard.

## Evaluation Dimensions

| Dimension | Weight | What it measures |
|-----------|--------|------------------|
| Write precision | 15% | Ratio of high-signal records to total active records. Noise events should be filtered. |
| Retrieval precision | 15% | Whether expected records appear in top-5 retrieval results for labeled queries. |
| Expected-answer coverage | 15% | Whether retrieved memories cover the fixture's expected answer terms, not only the expected title. |
| Latency | 10% | Consolidation time. Penalizes runs exceeding 1 second. |
| Concurrency safety | 15% | Structural guarantee via single-writer file lock. Tested separately. |
| Contradiction handling | 10% | Whether contradictory events produce contested or superseded records rather than silent overwrite. |
| Procedural reuse / workflow memory | 10% | Whether required workflow memories are active procedural records with extracted workflow steps. |
| Gating accuracy | 10% | Whether short/noise queries are correctly gated (skipped) rather than retrieving irrelevant memories. |

## Scoring Formula

```
weighted_total = write_precision * 0.15
              + retrieval_precision * 0.15
              + expected_answer_coverage * 0.15
              + latency * 0.10
              + concurrency_safety * 0.15
              + contradiction_handling * 0.10
              + procedural_reuse * 0.10
              + gating_accuracy * 0.10
```

## Pass/Fail Thresholds

- `weighted_total >= 80`: overall pass
- `write_precision >= 60`: minimum write quality
- `retrieval_precision >= 60`: minimum retrieval quality
- `expected_answer_coverage >= expected_answer_min_coverage`: retrieved context covers expected answers
- required workflow memories must be present as procedural records with workflow steps

All conditions must be met for a passing scorecard.

## Fixture Design

The evaluation uses `opendream/fixtures/performance_eval.json` containing:

- **High-signal events** (5): project decisions, environment requirements, procedural workflows, user preferences — each with clear expected durable record titles
- **Noise events** (3): low-information-density events that should be filtered by salience scoring
- **Contradiction events** (1): events that contradict earlier high-signal events, testing contradiction resolution
- **Coverage gate**: requires expected answers on should-match queries and at least one required workflow memory
- **Should-match queries** (4): queries with expected title and answer matches, testing retrieval precision and answer coverage
- **Should-gate queries** (2): short or noise-only queries that should trigger retrieval gating

## Execution Model

The eval is **hermetic**: it creates an isolated empty memory store so existing durable memory cannot skew results. The sequence is:

1. Emit high-signal + noise events
2. Run consolidation (maintain)
3. Emit contradiction events
4. Run consolidation again
5. Score write precision against expected titles
6. Run retrieval queries and score title precision plus expected-answer coverage
7. Verify required workflow memories are procedural and task-shaped
8. Run gating queries and score accuracy
9. Compute latency metrics
10. Produce composite scorecard

## Known Limitations

1. **Fixture-driven, not ecological**: Results demonstrate capability on controlled inputs, not real-world diversity. External-repo benchmarks are future work.
2. **Small scale**: 9 events total. Behavior at 1000+ events is not benchmarked.
3. **Deterministic**: The fixture produces consistent scores. This is intentional for CI reliability but does not capture variance.
4. **Concurrency score is structural**: Set to 100 because the lock mechanism is tested separately via integration tests, not exercised in the performance eval itself.

## How to Run

```bash
# Standalone
opendream eval performance --workspace .tmp/eval

# As part of verification (includes all stages)
make verify

# Full release check (includes scorecard in manifest)
make release-check
```

Output is JSON to stdout. Non-zero exit on failure.

## Interpreting Results

The scorecard JSON includes:
- `scorecard`: per-dimension scores and weighted total
- `details`: raw counts (events emitted, records created, noise filtered, etc.)
- `latency`: timing for emit, maintain, and retrieval operations
- `retrieval_results`: per-query hit/miss with selected titles
- `gating_results`: per-query gating correctness
