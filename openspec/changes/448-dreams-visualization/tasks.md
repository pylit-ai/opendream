# Tasks

## P0 — backend projections + narrative
- [x] add `_build_dream_cycle_projection(run)` in `observability.py`
- [x] add `opendream/dream_narrative.py` with deterministic template synthesizer
- [x] persist `narrative` field into the dream run record after each cycle
- [x] backfill: `opendream dream backfill-narrative --workspace <ws>`
- [x] unit tests cover every narrative template branch
- [x] regression: existing dream tests still pass

## P0 — phase traces
- [x] promote per-phase timings to top-level `run.phase_traces`
- [x] each entry: `{name, started_at, ended_at, duration_ms, summary?}`
- [x] integration test asserts non-zero `duration_ms` per phase

## P0 — read endpoints
- [x] `GET /api/dream/cycles?limit&since` — projection list
- [x] `GET /api/dream/cycles/:run_id` — full detail with traces + narrative
- [x] `GET /api/dream/coverage?window=7d` — bucketed source mix
- [x] `GET /api/dream/funnel?window=7d` — per-cycle funnel counts
- [x] all endpoints honor in-process index cache (no extra disk scan)

## P0 — frontend layout
- [x] `frontend/src/components/dreams/PhaseBar.tsx` — stacked SVG widget
- [x] `frontend/src/components/dreams/Funnel.tsx` — vertical funnel widget
- [x] `frontend/src/components/dreams/CoverageTrend.tsx` — inline SVG line chart
- [x] refactor Dreams page to use new widgets
- [x] cycle row sub-line shows narrative
- [x] detail SlideOver gets narrative paragraph + chart widgets

## P0 — verification
- [x] perf: `/api/dream/cycles?limit=50` p95 < 100ms warm cache
- [x] e2e: Dreams page first paint < 600ms; empty workspace renders gracefully
- [x] zero new dependencies in `frontend/package.json`

## P1 — agent neutrality
- [x] grep `claude` across frontend; replace with neutral phrasing
- [x] tooltip lists supported runtimes (Claude Code auto; Codex/Cursor/Gemini via `--from`)
- [x] update transcripts module to also auto-detect Codex sessions when path is well-known

## P1 — docs
- [x] `docs/automation/dream-task-playbook.md` — "Reading the Dreams page" section
- [x] `docs/architecture/dream-narrative.md` — template inventory + extension hooks
- [x] update `docs/architecture/overview.md` with the new endpoints

## P2 — future work
- [ ] LLM-backed narrative summarizer (opt-in; same template fallback if disabled)
- [ ] real-time SSE for cycle completion events
- [ ] per-memory dream provenance heatmap
