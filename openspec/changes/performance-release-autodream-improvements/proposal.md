# performance-release-autodream-improvements

## Why

OpenDream has a mature core runtime (event capture, consolidation, retrieval, dream engine, worker, observability) that already exceeds AutoDream's publicly documented capabilities in several areas: auditable diffs, plan/verifier artifacts, concurrency safety, and structured conflict resolution. However, AutoDream's known weaknesses—and the 2026 survey's engineering checklist—expose concrete improvement opportunities in five areas where OpenDream can verifiably outperform: write-path filtering quality, retrieval gating, procedural memory, performance instrumentation, and memory-hurt attribution. Shipping these improvements with measurable evidence positions OpenDream as the performance-first alternative, not a clone.

## Goal

Ship a performance release that verifiably improves long-horizon coding-agent throughput by:

1. Adding a performance harness that measures task-success delta, latency, token cost, irrelevant recall rate, and contradiction resolution accuracy.
2. Improving write-path filtering with salience scoring, novelty detection against durable state, and per-kind acceptance thresholds.
3. Adding retrieval gating (skip retrieval on easy turns) and staged retrieval (fast prefilter → optional rerank).
4. Upgrading procedural memory to extract, represent, and reuse workflows separately from semantic facts.
5. Adding memory-hurt instrumentation to detect when recalled memory was stale, contradicted, or ignored.

## Non-goals

- AutoDream path/layout/command parity
- UI cosmetic parity with Claude Code `/memory`
- Vector database or embedding service dependencies
- Remote/hosted consolidation
- Model-backed consolidation upgrades (deferred until harness proves value)

## Success criteria

- Performance harness runs as part of `make verify` and produces a machine-readable scorecard.
- Write precision on labeled eval corpora is measurably higher than baseline (pre-change).
- Retrieval gating reduces unnecessary recall on simple queries by ≥30%.
- Procedural workflows are extracted, stored separately, and retrievable by task type.
- Memory-hurt events are logged and classifiable into write-path, retrieval-path, or reasoning-layer buckets.
- All existing tests continue to pass; no regressions in dream-fidelity or memory-quality evals.
- Release scorecard (per planning.md rubric) reaches ≥80.

## Verifiable improvements over AutoDream

| Dimension | AutoDream (public evidence) | OpenDream (current) | OpenDream (this release) |
|---|---|---|---|
| Write-path filtering | Unknown heuristic; no public salience scoring | Semantic clustering + dedup | + salience classifier, novelty scoring, per-kind thresholds |
| Retrieval | Full memory load at startup; no gating | Lexical + semantic scoring with type/recency priors | + retrieval gating, staged retrieval, adaptive token budget |
| Concurrency safety | No locking (GitHub #24130) | File-based single-writer lock, stale-lock recovery | Same (already superior) |
| Audit trail | "Writing memory" with no diff (GitHub #23176) | Full diff + plan + verifier artifacts per run | + memory-hurt attribution logging |
| Contradiction handling | Unknown; cleanup in dream phase | Supersede/contested status, temporal validity | + explicit contradiction resolution accuracy metric |
| Procedural memory | Scoped to memory-file cleanup only | Typed candidates include `procedural_workflow` | + dedicated workflow extraction, representation, and reuse |
| Performance measurement | None public | dream-fidelity + memory-quality evals | + full performance harness with task-success delta |
