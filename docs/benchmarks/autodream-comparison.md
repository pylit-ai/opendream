# Managed-Memory Compatibility Benchmark Note

**Last verified**: 2026-03-31
**Compatibility reference**: public docs and public issue reports available on
the verification date
**OpenDream reference**: v0.2.0

---

## Methodology

This note uses public compatibility evidence and verifiable OpenDream behavior
(code, tests, eval results). It does not use leaked prompts, private docs,
private fixtures, or non-public implementation details. Where external behavior
is inferred rather than documented, that is noted.

**How to reproduce OpenDream results:**

```bash
uv tool install opendream  # or: pip install opendream
opendream eval performance --workspace .tmp/eval
make verify  # from repo checkout — includes performance-eval stage
```

---

## Comparison Table

| Dimension | External managed-memory behavior | OpenDream | Verdict |
|-----------|-----------|-----------|---------|
| Write-path filtering | Publicly documented detail is limited | Salience scoring + novelty detection + per-kind thresholds | OpenDream: measurable fixture behavior |
| Retrieval strategy | Public docs describe startup memory loading | Hybrid lexical+semantic, retrieval gating, staged rerank | OpenDream: measured on packaged fixtures |
| Concurrency safety | Public issue reports describe write-conflict risk | File-based single-writer lock with TTL | OpenDream: covered by tests |
| Audit trail | Public reports describe limited write visibility | Full diff + plan + verifier artifacts per consolidation run | OpenDream: auditable locally |
| Contradiction handling | Unknown (inferred: newer overwrites older) | Temporal validity windows, superseded/contested status, quarantine | OpenDream: non-destructive, traceable |
| Procedural memory | Scoped to memory file cleanup only | Dedicated extraction of workflow steps, typed procedural records | OpenDream: reusable workflows |
| Performance measurement | None publicly available | Composite scorecard: write precision, retrieval precision, expected-answer coverage, latency, gating, contradiction, workflow memory | OpenDream: measurable |

---

## Detailed Analysis

### 1. Write-Path Filtering

**External managed-memory behavior**: Public behavior suggests between-session
memory maintenance, but write heuristics are not publicly specified. OpenDream
does not use leaked prompts or private implementation details for this note.

**OpenDream**: Candidates are scored via `score_salience()` combining novelty (Jaccard distance against existing records), information density, and type prior weights. Per-kind minimum thresholds are configurable in store config. Noise events (low density, high overlap) are filtered before consolidation. Tested via `eval performance` write precision rubric — current score: **100/100**.

**Evidence**: `opendream/extractor.py:score_salience()`, `opendream/fixtures/performance_eval.json` (noise events filtered), verification report stage `performance-eval`.

### 2. Retrieval Strategy

**External managed-memory behavior**: Public docs describe startup memory
loading. Query-time gating or adaptive retrieval behavior is not specified in
the public references used for this note.

**OpenDream**: Three-stage retrieval: (1) compact startup index, (2) query-time hybrid BM25 + semantic scoring with type/recency filters, (3) optional rerank for ambiguous results. Retrieval gating skips retrieval entirely for very short queries or noise-only tokens. Current retrieval precision: **100/100**, gating accuracy: **100/100**.

**Evidence**: `opendream/retriever.py:retrieve()`, `opendream/retriever.py:should_retrieve()`, eval performance gating results.

### 3. Concurrency Safety

**External managed-memory behavior**: Public issue reports describe possible
write conflicts in file-backed memory workflows.

**OpenDream**: Single-writer file lock with configurable TTL. Lock contention returns explicit skip results rather than silent corruption. Dream runs detect held locks and exit cleanly. Tested via `test_dream_run_skips_when_lock_is_held` and `test_single_writer_lock_exits_cleanly`.

**Evidence**: `opendream/storage.py:FileLock`, integration tests in `tests/test_memory_cli.py`.

### 4. Audit Trail

**External managed-memory behavior**: Public reports describe limited
write-diff visibility.

**OpenDream**: Every consolidation run produces:
- A plan artifact (what the consolidator intends to do)
- A verifier artifact (what actually happened)
- A diff file (exact before/after)
- A summary JSON (counts, statuses, run ID)
- Memory-hurt audit logging (stale/contradicted/low-confidence recalls)

All artifacts are persisted under `<memory-root>/audit/` and surfaced via the observability UI.

**Evidence**: `opendream/consolidator.py`, `opendream/observability.py`, `<memory-root>/audit/consolidation/` on any consolidation run.

### 5. Contradiction Handling

**External managed-memory behavior**: Contradiction handling is not specified in
the public references used for this note.

**OpenDream**: Records use temporal validity windows and explicit status transitions: `active` → `superseded` (replaced by newer evidence), `contested` (conflicting claims, both plausible), or `quarantined` (flagged for review). Superseded records are retained for provenance. Contradiction resolution score: **100/100** in performance eval.

**Evidence**: `opendream/consolidator.py` status transitions, `opendream/models.py` status enum, eval performance contradiction handling.

### 6. Procedural Memory

**External managed-memory behavior**: Publicly visible behavior focuses on
memory-file maintenance. Workflow extraction is not documented in the public
references used for this note.

**OpenDream**: Dedicated `procedural_workflow` memory type with `workflow_steps` field. The extractor parses numbered and bulleted step sequences from procedural content. Workflows are stored separately from semantic facts and retrievable by task type. Procedural reuse score: **100/100**.

**Evidence**: `opendream/extractor.py` workflow step parsing, `opendream/models.py` MemoryCandidate.workflow_steps, eval performance procedural_reuse.

### 7. Performance Measurement

**External managed-memory behavior**: No public performance harness, scorecard,
or benchmark methodology was available in the references used for this note.

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

1. **No live A/B comparison**: We cannot run external managed-memory systems
   programmatically for this note. External claims are based on public evidence,
   not side-by-side runtime testing.

2. **Fixture-driven evaluation**: The current benchmark uses controlled fixtures, not held-out workloads from diverse real-world repos. Fixture results demonstrate capability but not ecological validity.

3. **No external cost/latency accounting**: We cannot measure latency or token
   cost for external managed-memory systems from this repository.

4. **Memory-hurt scenarios**: The memory-hurt audit logs when recalled memory was stale or contradicted, but we have not yet quantified the net positive/negative impact of memory on downstream task success across diverse workloads.

5. **Scale testing**: Current evaluation uses small fixtures (5-9 events). Behavior at 1000+ events across months of sessions has not been benchmarked.

### What would close these gaps

- **External repo benchmark suite**: Run OpenDream on 3-5 public repos with realistic task sequences and measure task-success delta with/without memory.
- **External behavior documentation**: If external systems publish trigger
  thresholds and write heuristics, update this note with specific numbers.
- **Adversarial memory cases**: Deliberately test scenarios where memory should hurt (stale decisions, outdated environment info, contradicted preferences) and measure recovery.

---

## References

### Public compatibility sources
- [Claude Code memory docs](https://code.claude.com/docs/en/memory) — official storage layout, MEMORY.md behavior
- [GitHub #39135](https://github.com/anthropics/claude-code/issues/39135) — /dream shown in UI but not recognized
- [GitHub #39204](https://github.com/anthropics/claude-code/issues/39204) — auto-dream ignores autoMemoryDirectory
- [GitHub #24130](https://github.com/anthropics/claude-code/issues/24130) — no concurrency control for auto-memory
- [GitHub #23176](https://github.com/anthropics/claude-code/issues/23176) — memory writes hidden, no diff

### OpenDream sources
- `opendream/evaluation.py` — performance eval implementation
- `opendream/retriever.py` — retrieval and gating
- `opendream/consolidator.py` — consolidation and contradiction handling
- `opendream/storage.py` — file locking
- `scripts/verify.py` — verification pipeline with performance gate
- `tests/test_memory_cli.py` — 72 integration tests
