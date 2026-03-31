# Acceptance test matrix: performance-release-autodream-improvements

## Write-path quality

| # | Scenario | Expected | Status |
|---|---|---|---|
| W1 | Emit high-signal event (project_decision with unique content) | Created as durable record with salience > 0.5 | ✅ PASS |
| W2 | Emit low-signal event (semantic_fact with near-duplicate body) | Filtered by novelty scoring, not promoted to durable | ✅ PASS |
| W3 | Emit event below per-kind salience threshold | Candidate created but filtered before consolidation | ✅ PASS |
| W4 | Salience score reflects novelty against existing durable records | Novel content scores higher than duplicate content | ✅ PASS |
| W5 | Information density penalizes filler-heavy candidates | Short stopword-heavy body gets lower salience than dense body | ✅ PASS |

## Retrieval gating

| # | Scenario | Expected | Status |
|---|---|---|---|
| R1 | Very short query (1-2 tokens) | Gated, returns `{"gated": true}` | ✅ PASS |
| R2 | Query with only noise tokens | Gated, returns with reason | ✅ PASS |
| R3 | Normal query with content tokens | Not gated, proceeds to retrieval | ✅ PASS |
| R4 | Explicit `skip_retrieval=True` | Gated regardless of query content | ✅ PASS |

## Staged retrieval

| # | Scenario | Expected | Status |
|---|---|---|---|
| S1 | Clear top-1 winner (score ratio > threshold) | Rerank skipped, fast path only | ✅ PASS |
| S2 | Ambiguous top scores (ratio < threshold) | Full rerank triggered | ✅ PASS |
| S3 | Retrieval results identical for unambiguous queries | Same top-k in both paths | ✅ PASS |

## Procedural memory

| # | Scenario | Expected | Status |
|---|---|---|---|
| P1 | Emit procedural_workflow event with numbered steps | workflow_steps populated in candidate and record | ✅ PASS |
| P2 | Emit procedural_workflow event with bullet steps | workflow_steps populated | ✅ PASS |
| P3 | Emit procedural_workflow event with prose (no steps) | workflow_steps empty list | ✅ PASS |
| P4 | Retrieve by procedural query matches workflow records | Type boost surfaces workflows | ✅ PASS |

## Memory-hurt instrumentation

| # | Scenario | Expected | Status |
|---|---|---|---|
| H1 | Retrieve when durable records include stale entries | stale_recalled logged in audit | ✅ PASS |
| H2 | Retrieve with include_contested=True | contradicted_recalled logged | ✅ PASS |
| H3 | Low-confidence record in top-k | low_confidence_recalled logged | ✅ PASS |
| H4 | All recalled records are fresh and high-confidence | memory_hurt audit has empty lists | ✅ PASS |

## Performance harness

| # | Scenario | Expected | Status |
|---|---|---|---|
| E1 | `opendream eval performance` runs to completion | JSON scorecard output, exit 0 | ✅ PASS |
| E2 | Scorecard includes all rubric categories | write_precision, retrieval_precision, latency, contradiction, gating_accuracy present | ✅ PASS |
| E3 | Performance eval integrated into `make verify` | Deferred — runs standalone | ⏳ DEFERRED |
| E4 | Eval with fixture produces deterministic scores | Repeated runs yield same scores | ✅ PASS |

## Regression safety

| # | Scenario | Expected | Status |
|---|---|---|---|
| X1 | All existing 65 tests continue to pass | `make verify` PASS | ✅ PASS |
| X2 | dream-fidelity eval passes | No regression | ✅ PASS |
| X3 | memory-quality eval passes | No regression | ✅ PASS |
| X4 | New fields are backward-compatible | Existing records without workflow_steps load correctly | ✅ PASS |
