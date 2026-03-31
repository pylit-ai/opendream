# Design: performance-release-autodream-improvements

## Architecture decisions

### AD-1: Write-path salience scoring

Current extractor assigns salience as `min(1.0, confidence + 0.1)` — a near-passthrough from confidence. This means all events of the same kind get approximately the same salience regardless of actual information value.

**Change**: Add a `score_salience()` function in extractor.py that computes salience from three signals:
1. **Novelty**: Jaccard distance between candidate body and existing durable records. High overlap = low novelty = lower salience.
2. **Information density**: Ratio of non-stopword tokens to total tokens. Low-density candidates (mostly filler) get penalized.
3. **Type prior**: Keep existing type-based confidence as a floor.

Formula: `salience = clamp(0.1, 1.0, novelty_score * 0.5 + density_score * 0.3 + type_prior * 0.2)`

The novelty check requires reading durable records at extraction time. This is acceptable because extraction already runs during `maintain()` which holds no lock, and durable records are lock-free reads.

### AD-2: Per-kind acceptance thresholds

Add configurable minimum salience thresholds per candidate type in store config under `write_policy.min_salience`:

```json
{
  "write_policy": {
    "min_salience": {
      "semantic_fact": 0.4,
      "pending_item": 0.3,
      "user_preference": 0.2,
      "project_decision": 0.2,
      "procedural_workflow": 0.2,
      "anti_pattern": 0.3,
      "contested_fact": 0.1
    }
  }
}
```

Candidates below threshold are filtered before consolidation. This is the "aggressive filtering" the planning checklist demands.

### AD-3: Retrieval gating

Add a `should_retrieve()` gate in retriever.py that returns False when:
- Query token count is below a minimum threshold (very short/simple queries)
- Query contains only high-frequency noise tokens
- An explicit `skip_retrieval=True` flag is passed

When gated, `retrieve()` returns immediately with `{"gated": true, "reason": "..."}` and zero memory IDs. This reduces unnecessary recall on easy turns.

### AD-4: Staged retrieval

Split retrieval into two stages:
1. **Fast prefilter**: Lexical-only scoring (current lexical path). Cheap. Returns top-N candidates.
2. **Rerank** (optional): Full scoring (lexical + semantic + type + recency + confidence + salience). Only runs when prefilter ambiguity is high (top scores are close together, or many candidates tie).

The rerank threshold is configurable: `retrieval.rerank_ambiguity_threshold` (default 0.8 — if top-1 score / top-2 score > threshold, skip rerank).

### AD-5: Procedural memory extraction

Current extractor handles `procedural_workflow` as a candidate type but doesn't extract structured workflow steps.

**Change**: Add an optional `workflow_steps` field to MemoryCandidate and MemoryRecord. When a candidate is typed `procedural_workflow`, parse the body for numbered/bulleted steps and store them as a list. This enables:
- Retrieval filtered by workflow type
- Step-count metrics in evals
- Future workflow replay

The field is optional and backward-compatible (defaults to empty list).

### AD-6: Performance harness

Add `opendream eval performance` command that runs a composite evaluation:

1. **Write precision**: Emit labeled events (some high-signal, some noise). Measure what fraction of durable records are high-signal.
2. **Retrieval precision**: Query with known-answer questions. Measure top-k hit rate.
3. **Retrieval gating accuracy**: Include queries that should NOT trigger retrieval. Measure gate correctness.
4. **Latency**: Time each operation (emit, maintain, retrieve, dream-run). Report p50/p95.
5. **Token cost estimate**: Count characters in assembled context vs. stored memory. Lower ratio = better.
6. **Contradiction resolution**: Emit contradicting events. Verify supersede/contested behavior.

Output: JSON scorecard mapping to the planning.md rubric categories with 0-100 scores.

### AD-7: Memory-hurt instrumentation

Add a `memory_hurt` audit trail alongside the existing retrieval audit. After each retrieval, log:
- `stale_recalled`: records whose `updated_at` is older than a configurable staleness threshold
- `contradicted_recalled`: records with status `contested` that were still included
- `low_confidence_recalled`: records below a confidence threshold that made it into top-k

Store in `audit/memory_hurt/` as JSON. The eval harness reads these to produce a memory-hurt rate.

## Files modified

| File | Change |
|---|---|
| `opendream/extractor.py` | Add `score_salience()`, novelty scoring, per-kind filtering |
| `opendream/retriever.py` | Add `should_retrieve()` gate, staged retrieval, memory-hurt logging |
| `opendream/models.py` | Add `workflow_steps` to MemoryCandidate and MemoryRecord |
| `opendream/evaluation.py` | Add `run_performance_eval()` |
| `opendream/consolidator.py` | Pass durable records to extractor for novelty scoring |
| `opendream/integration.py` | Wire new eval command, pass store to extraction |
| `opendream/cli.py` | Add `eval performance` subcommand |
| `opendream/storage.py` | Add `write_memory_hurt_audit()`, config defaults for new settings |
| `opendream/fixtures/` | Add `performance_eval.json` fixture |
| `tests/test_memory_cli.py` | Add performance eval tests, write-filter tests, gating tests |
