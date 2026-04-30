# 448-dreams-visualization

## Why
Spec 446 (observability-perf) and the v1 Dreams page (shipped alongside it) gave operators a manual "Dream now" trigger and a basic cycle list. They still cannot answer the core questions a dream-driven memory system raises:

- **Where is time being spent?** Phase-by-phase, across cycles. Today the operator sees only total duration. They cannot tell whether `synthesize` is dominating or `gather_recent_signal` is starving.
- **Is the dream actually producing memory?** Today only individual proposal counts surface. There is no visible funnel from `families_considered → proposals_approved → memories_created`, no rolling success-rate, no cycle-over-cycle deltas.
- **Has my signal stream broken silently?** Spec 447 caught one failure mode (transcripts never wired). The next one will be subtle: hooks emit events but the events route to the wrong source class. Operators need a trend chart to spot signal-source drift before a week of dreams produces zero learning.
- **What did the agent actually do this cycle?** The Dreams detail panel now exposes structured counts, but operators still need a 1-2 sentence narrative summary they can scan in five seconds. Today the cycle is a wall of numbers; humans read prose faster.

The goal is a Dreams page operators trust to answer "is the system learning, and where is it stuck?" without tailing logs.

## Goal
Promote the Dreams page from cycle-list to cycle-observatory: visualize phase timing, the proposal funnel, signal-source coverage over time, and a per-cycle natural-language narrative. Make blocked cycles legible at a glance. Surface the same data via API for operators who script.

## What changes

### API additions (read-only, additive)
- `GET /api/dream/cycles` — projection of dream-class runs with curated dream fields (mode, model, costs, phase timings, funnel counts) without the heavy diff_text payload. Pagination via `?limit` `?since`.
- `GET /api/dream/cycles/:run_id` — full per-cycle detail including parsed `phase_traces` (start/end/duration per phase), funnel counts, and the narrative summary.
- `GET /api/dream/coverage?window=7d` — time-bucketed signal coverage. Returns rolling source-class breakdown (`explicit_events` vs `transcript_episodes` vs `automation`) so the operator can spot a hook regression.
- `GET /api/dream/funnel?window=7d` — per-cycle counts aggregated for trend lines.
- `POST /api/dream/run` (existing) — accept `narrative: true` flag to also emit a short prose summary. Falls through to existing behavior when omitted.

### Backend: phase traces + narrative
- Persist per-phase `(name, started_at, ended_at, duration_ms, summary_short)` records into the dream run output. Already collected by the dream pipeline; just preserve them on the run record at top level (`run.phase_traces`).
- After a successful cycle, compose a 1-2 sentence narrative summary into `run.narrative` (e.g. "Consolidated 4 contested memories into 1 superseder; pruned 11 low-confidence facts; signal source was claude-pre-task hooks.").
- Source the narrative deterministically from the existing summary dict (no LLM dependency for v1). Operators can later opt into an LLM-backed summarizer.

### Frontend: Dreams v2
- Replace the v1 "Recent dream cycles" table with a layout:
  - Top: **headline strip** — total cycles in window, success rate, avg duration, total proposals approved, signal-source mix donut.
  - **Phase progression panel** — small horizontal stacked bars (one per recent cycle, last 20) showing phase time breakdown. Hover/tap reveals exact ms per phase.
  - **Proposal funnel panel** — vertical stages (Considered → Selected → Generated → Approved → Created). Each stage shows count + percent of previous stage.
  - **Signal coverage trend** — small line chart of source-class share over time.
  - **Cycle list** — same as v1 but with the new `narrative` line under run_id, and a `phase_durations` mini-bar inline with the Phases column.
  - **Skipped-cycle inspector** retained.
- Detail SlideOver gains a **narrative paragraph** at the top, the phase timeline as a vertical bar chart instead of just an ordered list, and the proposal funnel rendered as the same widget the page-level panel uses.

### Frontend: agent neutrality
- Replace remaining Claude-specific copy ("Claude Code session JSONLs") with agent-agnostic phrasing ("agent transcripts"). Auto-detect remains scoped to Claude for now; CLI `--from` covers the rest. Tooltip lists supported runtimes.

## Non-goals
- LLM-backed summarization (deferred — deterministic prose is enough for v1; an LLM step is a follow-on).
- New chart library. Pure CSS / SVG inline. No d3/recharts dependency.
- Per-memory dream provenance heatmap (item 3 from the v0 outline).
- Real-time cycle streaming. Polling stale-while-revalidate is fine.

## Success criteria
- An operator can answer "is the dream system learning?" within ten seconds of opening Dreams.
- The narrative line tells a non-technical reader the cycle outcome in one sentence.
- A broken signal source produces a visible dip in the coverage trend within 24h, not a week.
- p95 `/api/dream/cycles` < 100ms with the index cache warm; full Dreams page first paint < 600ms.
- Zero new heavy dependencies in `frontend/package.json`.
