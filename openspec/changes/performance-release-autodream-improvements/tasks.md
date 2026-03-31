# Tasks: performance-release-autodream-improvements

## WS1: Write-path quality improvements

- [x] T1: Add `score_salience()` to extractor.py with novelty, density, length, and type-prior signals
- [x] T2: Add per-kind minimum salience thresholds to store config defaults
- [x] T3: Filter candidates below threshold before consolidation in integration.py
- [x] T4: Verified via existing tests + performance eval (noise filtered, high-signal retained)

## WS2: Retrieval gating and staged retrieval

- [x] T5: Add `should_retrieve()` gating function to retriever.py
- [x] T6: Implement staged retrieval (fast prefilter → optional rerank)
- [x] T7: Add `rerank_ambiguity_threshold` config option
- [x] T8: Verified via performance eval gating tests (100% gating accuracy)

## WS3: Procedural memory upgrade

- [x] T9: Add `workflow_steps` field to MemoryCandidate and MemoryRecord models
- [x] T10: Parse workflow steps from procedural_workflow candidate bodies in extractor
- [x] T11: Verified via performance eval (procedural_reuse = 100%)

## WS4: Memory-hurt instrumentation

- [x] T12: Add `write_memory_hurt_audit()` to storage.py
- [x] T13: Log stale, contradicted, and low-confidence recalls in retriever.py
- [x] T14: Verified via retriever memory_hurt payload in all retrieval responses

## WS5: Performance harness

- [x] T15: Create `performance_eval.json` fixture with labeled events and queries
- [x] T16: Implement `run_performance_eval()` in evaluation.py
- [x] T17: Wire `eval performance` CLI subcommand
- [ ] T18: Add performance eval to `make verify` pipeline (deferred — runs standalone)
- [x] T19: Verified via direct invocation (scorecard: 99.8/100)

## WS6: Release validation

- [x] T20: Run full `make verify` — all 65 tests pass, all stages PASS
- [ ] T21: Run `make release-check` (requires clean venv rebuild)
- [x] T22: Performance scorecard reaches 99.8 (≥80 threshold met)
