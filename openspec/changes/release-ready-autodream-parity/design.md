## Context

OpenDream's memory runtime is at 89/100 with all performance improvements implemented. The performance eval (`eval performance`) exists and scores 99.8/100, but it runs standalone — not as part of `make verify` or `make release-check`. AutoDream is now confirmed as a 4-phase background consolidation pipeline (orient → gather → consolidate → prune) running every ~24h after 5+ sessions. OpenDream already exceeds AutoDream on concurrency safety (single-writer lock vs none), audit trails (full diff + plan + verifier vs "Writing memory" with no diff), contradiction handling (supersede/contested/temporal vs unknown), and procedural memory (dedicated extraction/reuse vs memory cleanup only). These advantages are implemented but not yet provable via automated release gates or documented for external scrutiny.

The `specs/registry.yaml` has 26 entries and some show status drift vs actual implementation state. The performance-release change has 19/22 tasks done with 3 deferred (notably: `eval performance` not in `make verify`). The 436 agent-ready-platform change is 12/55 tasks done.

## Goals / Non-Goals

**Goals:**

1. Make `eval performance` a blocking stage in `make verify` so the scorecard is release proof
2. Archive the performance scorecard in `make release-check` manifest
3. Create a documented AutoDream comparison methodology with dimension-by-dimension analysis
4. Expand eval evidence beyond current fixtures with realistic task patterns
5. Reconcile spec/registry state drift for governance hygiene
6. Document honest improvements AND limitations vs AutoDream
7. Ensure the quickstart path works reliably in under 5 minutes

**Non-Goals:**

- Completing the full 436 agent-ready-platform bundle (WS5-WS9 remain separate work)
- Building a hosted demo or web-based tryout
- Changing the license (that decision is orthogonal)
- Vector database integration or remote consolidation
- Model-backed consolidation (deferred)
- Publication-grade repeated-trial benchmark with cost normalization (future work; this change creates the harness and methodology, not the full statistical campaign)

## Decisions

### D1: Performance eval integration approach

**Choice**: Add `eval performance` as a new stage in `scripts/verify.py` using the same hermetic temp-workspace pattern as `dream-fidelity-eval`. Add scorecard archival to `scripts/release_check.py`.

**Why not inline into existing tests**: The performance eval is a composite harness with its own scorecard, not a unit test. It needs its own stage identity for diagnostics and should block independently with a clear threshold failure message.

**Why not a separate CI job**: The repo uses `make verify` as the single authoritative gate. Adding a parallel job would fragment the release proof.

### D2: AutoDream comparison harness

**Choice**: Create a static comparison document at `docs/benchmarks/autodream-comparison.md` with a dimension-by-dimension table, methodology, evidence references, and reproduction instructions. The comparison is evidence-based (referencing public AutoDream info + OpenDream eval results) rather than runtime-based (we cannot run AutoDream programmatically).

**Why not a runtime A/B harness**: AutoDream is not available as a standalone API. It runs inside Claude Code with server-side feature flags. A fair runtime comparison would require Anthropic cooperation or reverse-engineering their internal scheduler. Instead, we compare documented capabilities and measurable properties.

### D3: Eval corpus expansion

**Choice**: Add a `performance_eval_extended.json` fixture alongside the existing one, covering additional task archetypes: environment gotchas, multi-step workflows, conflicting decisions across time, and high-noise low-signal sessions. The extended fixture is consumed by `eval performance` when present.

**Why not external repos**: External repo benchmarks require network access, are non-deterministic, and break hermetic verification. Fixture-driven expansion gives us controlled diversity without CI fragility.

### D4: Registry reconciliation

**Choice**: Audit `specs/registry.yaml` against actual spec file states. Update status fields to match reality. Archive or mark superseded any specs that claim "active" but are actually implemented or replaced.

**Why not automated drift detection**: The registry has 26 entries and reconciliation is a one-time audit. Automated detection would be over-engineering for this scope.

### D5: Scorecard in release manifest

**Choice**: Run `eval performance` in `release_check.py` after the verify stage, capture the scorecard JSON, and include it in `release_manifest.json` under a `performance_scorecard` key.

**Why alongside verify rather than inside it**: The release check already runs verify as a stage. Adding performance eval to verify means it runs in both paths. The scorecard in the manifest provides archived evidence specific to the release artifact.

## Risks / Trade-offs

- **[Risk] Performance eval adds ~5-10s to verify time** → Acceptable; the eval is lightweight and fixture-driven. Timeout budget (240s default) has ample headroom.
- **[Risk] AutoDream comparison becomes stale as Anthropic updates** → Include a "last verified" date and version reference. The comparison is a point-in-time document, not a live dashboard.
- **[Risk] Extended fixture may not cover real-world diversity** → Explicitly scope as "controlled diversity" and note that external-repo benchmarks are future work.
- **[Risk] Registry reconciliation may surface incomplete specs** → That is the point. Better to surface it now than ship with governance drift.
