# 438-session-lifecycle-audit

## Why
The Sessions page shows dozens of sessions with `event_count = 0` or `1`. This contradicts the mental model of a session: an agent's logical interaction span, expected to bundle many events (context assembly, retrievals, run lifecycle, completion). Either:
- session IDs are minted per-call instead of per agent run, fragmenting one logical session across many records, or
- the event aggregator drops events when their `session_id` reference does not match a recorded session boundary, or
- session boundaries are recorded but events emitted around them carry a different (or missing) session_id.

Without trustworthy session aggregation, the Timeline view is misleading and downstream features (retrieval-attribution, agent-time analytics) sit on broken ground.

## Goal
Establish a documented, verifiable session lifecycle. Every retrieval, run, and context-assembly event recorded during an agent's interaction must roll up into exactly one session record, with start/end timestamps and an accurate `event_count`.

## What changes
- audit existing session minting points across `MemoryStore`, `observability.py`, and CLI hook adapters; produce a written event-flow doc
- if multiple call sites mint independent session IDs, introduce a single canonical `session_id` source (e.g. claude-pre-task hook output, or a session contextvar) and route all emitters through it
- if events are dropped during aggregation, fix the join logic in `_recent_sessions` / `query_sessions`
- add a session-integrity invariant test: spawn N events with controlled `session_id`s and assert each session record's `event_count` equals the number of emitted events
- add `/api/sessions/diagnostics` returning orphan event counts (events with `session_id` not matching any session record) for ongoing health
- update Sessions Timeline UI to surface session integrity warnings when `event_count == 0` (with a link to the diagnostics doc)

## Non-goals
- changing session storage layout
- introducing distributed session correlation across machines
- fixing pre-existing 0-event sessions in current data (tooling will let operators delete or merge them)

## Success criteria
- documented end-to-end event flow with a sequence diagram in `docs/architecture/`
- 0 sessions with `event_count == 0` in a freshly captured workspace
- `/api/sessions/diagnostics` returns 0 orphan events under steady-state operation
- one canonical session_id minter; no other call site invents new IDs without going through it
