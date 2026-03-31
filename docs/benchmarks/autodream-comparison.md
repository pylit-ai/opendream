# OpenDream vs AutoDream: Dimension-by-Dimension Comparison

**Last verified**: 2026-03-31
**AutoDream reference**: Claude Code v2.1.83+ (server-side feature flag rollout)
**OpenDream reference**: v0.2.0

---

## Methodology

This comparison uses publicly available evidence about AutoDream (official docs, GitHub issues, public analysis, extracted prompts) and verifiable OpenDream behavior (code, tests, eval results). Where AutoDream behavior is inferred rather than documented, that is noted.

**How to reproduce OpenDream results:**

```bash
uv tool install opendream  # or: pip install opendream
opendream eval performance --workspace .tmp/eval
make verify  # from repo checkout — includes performance-eval stage
```

---

## Comparison Table

| Dimension | AutoDream | OpenDream | Verdict |
|-----------|-----------|-----------|---------|
| Write-path filtering | Unknown heuristic | Salience scoring + novelty detection + per-kind thresholds | OpenDream: measurable, configurable |
| Retrieval strategy | Full memory load at session start; no query-time gating | Hybrid lexical+semantic, retrieval gating, staged rerank | OpenDream: adaptive, token-efficient |
| Concurrency safety | No locking ([GitHub #24130](https://github.com/anthropics/claude-code/issues/24130)) | File-based single-writer lock with TTL | OpenDream: safe for concurrent agents |
| Audit trail | "Writing memory" with no diff ([GitHub #23176](https://github.com/anthropics/claude-code/issues/23176)) | Full diff + plan + verifier artifacts per consolidation run | OpenDream: fully auditable |
| Contradiction handling | Unknown (inferred: newer overwrites older) | Temporal validity windows, superseded/contested status, quarantine | OpenDream: non-destructive, traceable |
| Procedural memory | Scoped to memory file cleanup only | Dedicated extraction of workflow steps, typed procedural records | OpenDream: reusable workflows |
| Performance measurement | None publicly available | Composite scorecard: write precision, retrieval precision, latency, gating, contradiction, procedural reuse | OpenDream: measurable |

---

## Detailed Analysis

### 1. Write-Path Filtering

**AutoDream**: The 4-phase pipeline (orient → gather → consolidate → prune) processes memory files between sessions. The write heuristic is not publicly documented. The leaked dream prompt suggests semantic deduplication and date normalization but does not expose confidence scoring or per-kind thresholds. ([Gist](https://gist.github.com/theramjad/1d3d4cbfbc7bf92c870b0bf79530e5fc))

**OpenDream**: Candidates are scored via `score_salience()` combining novelty (Jaccard distance against existing records), information density, and type prior weights. Per-kind minimum thresholds are configurable in store config. Noise events (low density, high overlap) are filtered before consolidation. Tested via `eval performance` write precision rubric — current score: **100/100**.

**Evidence**: `opendream/extractor.py:score_salience()`, `opendream/fixtures/performance_eval.json` (noise events filtered), verification report stage `performance-eval`.

### 2. Retrieval Strategy

**AutoDream**: Official docs state the first 200 lines of `MEMORY.md` are loaded at session start; topic files are fetched lazily. No query-time gating or adaptive retrieval is documented. ([Claude Code memory docs](https://code.claude.com/docs/en/memory))

**OpenDream**: Three-stage retrieval: (1) compact startup index, (2) query-time hybrid BM25 + semantic scoring with type/recency filters, (3) optional rerank for ambiguous results. Retrieval gating skips retrieval entirely for very short queries or noise-only tokens. Current retrieval precision: **100/100**, gating accuracy: **100/100**.

**Evidence**: `opendream/retriever.py:retrieve()`, `opendream/retriever.py:should_retrieve()`, eval performance gating results.

### 3. Concurrency Safety

**AutoDream**: Auto-memory writes are plain file edits without built-in concurrency control. This is a known issue. ([GitHub #24130](https://github.com/anthropics/claude-code/issues/24130))

**OpenDream**: Single-writer file lock with configurable TTL. Lock contention returns explicit skip results rather than silent corruption. Dream runs detect held locks and exit cleanly. Tested via `test_dream_run_skips_when_lock_is_held` and `test_single_writer_lock_exits_cleanly`.

**Evidence**: `opendream/storage.py:FileLock`, integration tests in `tests/test_memory_cli.py`.

### 4. Audit Trail

**AutoDream**: Memory writes display "Writing memory" in the UI without showing what changed. Users cannot see diffs. ([GitHub #23176](https://github.com/anthropics/claude-code/issues/23176))

**OpenDream**: Every consolidation run produces:
- A plan artifact (what the consolidator intends to do)
- A verifier artifact (what actually happened)
- A diff file (exact before/after)
- A summary JSON (counts, statuses, run ID)
- Memory-hurt audit logging (stale/contradicted/low-confidence recalls)

All artifacts are persisted under `<memory-root>/audit/` and surfaced via the observability UI.

**Evidence**: `opendream/consolidator.py`, `opendream/observability.py`, `<memory-root>/audit/consolidation/` on any consolidation run.

### 5. Contradiction Handling

**AutoDream**: The leaked prompt mentions "contradiction cleanup" but the specific mechanism is not documented. Behavior is inferred as newer-overwrites-older based on the dream prompt's instruction to "remove outdated information." ([Extracted prompt](https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/agent-prompt-dream-memory-consolidation.md))

**OpenDream**: Records use temporal validity windows and explicit status transitions: `active` → `superseded` (replaced by newer evidence), `contested` (conflicting claims, both plausible), or `quarantined` (flagged for review). Superseded records are retained for provenance. Contradiction resolution score: **100/100** in performance eval.

**Evidence**: `opendream/consolidator.py` status transitions, `opendream/models.py` status enum, eval performance contradiction handling.

### 6. Procedural Memory

**AutoDream**: Scoped to memory file cleanup — consolidation, deduplication, date normalization. Does not extract reusable workflows or debugging routines. ([Threads](https://www.threads.com/%40sakeeb.rahman/post/DWSKmNpkahx/))

**OpenDream**: Dedicated `procedural_workflow` memory type with `workflow_steps` field. The extractor parses numbered and bulleted step sequences from procedural content. Workflows are stored separately from semantic facts and retrievable by task type. Procedural reuse score: **100/100**.

**Evidence**: `opendream/extractor.py` workflow step parsing, `opendream/models.py` MemoryCandidate.workflow_steps, eval performance procedural_reuse.

### 7. Performance Measurement

**AutoDream**: No public performance harness, scorecard, or benchmark methodology.

**OpenDream**: Composite scorecard with weighted rubric:
- Write precision: 20%
- Retrieval precision: 20%
- Latency: 15%
- Concurrency safety: 15%
- Contradiction handling: 10%
- Procedural reuse: 10%
- Gating accuracy: 10%

Pass threshold: weighted total >= 80, write precision >= 60, retrieval precision >= 60. Current score: **99.8/100**. Integrated into `make verify` as a blocking release gate.

**Evidence**: `opendream/evaluation.py:run_performance_eval()`, `scripts/verify.py` performance-eval stage.

---

## Honest Limitations

### What OpenDream has NOT proven

1. **No live A/B comparison**: We cannot run AutoDream programmatically. All AutoDream claims are based on public evidence, not side-by-side runtime testing. A fair runtime comparison would require Anthropic cooperation.

2. **Fixture-driven evaluation**: The current benchmark uses controlled fixtures, not held-out workloads from diverse real-world repos. Fixture results demonstrate capability but not ecological validity.

3. **No cost/latency accounting vs AutoDream**: AutoDream runs inside Claude Code's infrastructure. We cannot measure its latency or token cost for comparison.

4. **Memory-hurt scenarios**: The memory-hurt audit logs when recalled memory was stale or contradicted, but we have not yet quantified the net positive/negative impact of memory on downstream task success across diverse workloads.

5. **Scale testing**: Current evaluation uses small fixtures (5-9 events). Behavior at 1000+ events across months of sessions has not been benchmarked.

### What would close these gaps

- **External repo benchmark suite**: Run OpenDream on 3-5 public repos with realistic task sequences and measure task-success delta with/without memory.
- **AutoDream behavioral capture**: If Anthropic documents AutoDream's trigger thresholds and write heuristics, update the comparison with specific numbers.
- **Adversarial memory cases**: Deliberately test scenarios where memory should hurt (stale decisions, outdated environment info, contradicted preferences) and measure recovery.

---

## References

### AutoDream sources
- [Claude Code memory docs](https://code.claude.com/docs/en/memory) — official storage layout, MEMORY.md behavior
- [GitHub #39135](https://github.com/anthropics/claude-code/issues/39135) — /dream shown in UI but not recognized
- [GitHub #39204](https://github.com/anthropics/claude-code/issues/39204) — auto-dream ignores autoMemoryDirectory
- [GitHub #24130](https://github.com/anthropics/claude-code/issues/24130) — no concurrency control for auto-memory
- [GitHub #23176](https://github.com/anthropics/claude-code/issues/23176) — memory writes hidden, no diff
- [Extracted dream prompt](https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/agent-prompt-dream-memory-consolidation.md) — 4-phase pipeline description
- [Dream prompt gist](https://gist.github.com/theramjad/1d3d4cbfbc7bf92c870b0bf79530e5fc) — consolidation prompt mirror

### OpenDream sources
- `opendream/evaluation.py` — performance eval implementation
- `opendream/retriever.py` — retrieval and gating
- `opendream/consolidator.py` — consolidation and contradiction handling
- `opendream/storage.py` — file locking
- `scripts/verify.py` — verification pipeline with performance gate
- `tests/test_memory_cli.py` — 72 integration tests
