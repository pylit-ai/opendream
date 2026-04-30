# Execution plan

## Phase 1 — backend projections + narrative
1. Add `_build_dream_cycle_projection(run)` in `observability.py` that returns the curated dream cycle shape (status, reason, mode, model, agent, started/ended, duration_ms, phases (timeline form), funnel counts, narrative).
2. Add a deterministic narrative synthesizer in `opendream/dream_narrative.py`:
   - Templates keyed by `summary.status × summary.reason × counts`. Examples:
     - completed + proposals_approved > 0: "Consolidated N proposals (M approved). Source: <signal_source>. Mode: <mode>."
     - completed + proposals_approved == 0: "No new proposals — workspace is stable. Scanned <signal_row_count> signal rows."
     - skipped + no-episodes: "Skipped — no transcripts available. Run `opendream transcripts ingest`."
     - skipped + insufficient-signal: "Skipped — recent transcripts didn't hit any orientation tokens."
   - Emit narrative into the saved run record, keyed `narrative`.
3. Backfill: a one-shot `opendream dream backfill-narrative --workspace <ws>` regenerates `narrative` for past runs.

## Phase 2 — phase traces
4. Wire `phase_traces` into the persisted run record top-level. The dream pipeline already emits per-phase timings to `summary` — promote them so list endpoints can serve them without descending into `summary`.
5. Each phase trace: `{ name, started_at, ended_at, duration_ms, summary }` (last field optional, short prose).
6. Test: dream-cycle integration test seeded with a known fixture asserts each phase row has both timestamps and a non-zero `duration_ms`.

## Phase 3 — read endpoints
7. `GET /api/dream/cycles[?limit=50&since=ISO]` — list of projections, no diff_text.
8. `GET /api/dream/cycles/:run_id` — full projection plus `phase_traces`, `narrative`, audit artifact paths.
9. `GET /api/dream/coverage?window=7d` — buckets by hour, returns `[{ts, by_source: {explicit_events, transcript_episodes, ...}, total}]`.
10. `GET /api/dream/funnel?window=7d` — per-cycle counts with `started_at`. Pure projection of summary fields.
11. All endpoints honor the in-process index cache; no new disk scans on the hot path.

## Phase 4 — frontend layout
12. Refactor `frontend/src/routes/Dreams.tsx`:
    - Top headline strip — pure CSS+SVG.
    - Phase progression: stacked-bar SVG widget. One row per cycle, segments by phase, color-coded.
    - Proposal funnel: vertical SVG funnel with stage labels + percent dropoff.
    - Signal coverage: tiny inline line chart (SVG path).
    - Cycle list: render `narrative` as a sub-line; mini-bar phase widget inline.
13. Detail SlideOver: add narrative paragraph at top, phase chart, funnel widget.
14. All new widgets pure SolidJS components in `frontend/src/components/dreams/` — no new dep.

## Phase 5 — agent neutrality + docs
15. Audit remaining Claude-specific copy across the frontend (`grep -i claude`). Replace with neutral phrasing + an explicit list of supported runtimes (Claude Code; Codex/Cursor/Gemini via `--from`).
16. Update `docs/automation/dream-task-playbook.md` with a "Reading the Dreams page" section.
17. Add `docs/architecture/dream-narrative.md` explaining the deterministic narrative templates so operators (and future LLM-backed extension) understand the mapping.

## Verification
- Unit: each narrative template branch has a fixture round-trip.
- Integration: ingest fixture transcripts → run a dream cycle → assert `/api/dream/cycles/<id>` returns expected shape including `phase_traces` and `narrative`.
- Perf: `/api/dream/cycles?limit=50` p95 < 100ms with cache warm.
- E2E: Dreams page first paint < 600ms; widgets render with no console errors on 0-cycle workspaces (graceful empty states).

## Rollout + rollback
- Phase 1+2 ship first. Phase 3-4 follow when projections are stable.
- Frontend Dreams v2 is feature-gated by presence of `/api/dream/cycles`; falls back to v1 cycle-list when 404.
- Rollback: revert frontend to v1 component; backend additions are additive and read-only.
