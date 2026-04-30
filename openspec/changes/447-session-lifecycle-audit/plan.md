# Execution plan

## Phase 1 — audit
1. Grep every call site that writes a `session_id` to the store (events, retrievals, runs, context assemblies). Catalog: who mints, who passes through, who drops.
2. Write `docs/architecture/session-lifecycle.md` with a sequence diagram covering claude-pre-task hook → context assembly → retrieval → run → claude-post-task hook.
3. Identify every gap: (a) sites that mint a fresh session_id when they should reuse, (b) sites that omit session_id entirely, (c) aggregator joins that filter out valid events.

## Phase 2 — single canonical minter
4. Introduce `opendream.sessions.current_session_id()` backed by a contextvar + persistent file token, so concurrent tasks each see their own session and idle processes can recover the active session from the workspace.
5. Update claude-pre-task and codex-pre-task hooks to set the contextvar + write the token; post-task hooks clear it.
6. Migrate every existing emit path to read the canonical session_id; remove ad-hoc minting.

## Phase 3 — aggregator correctness
7. Re-derive `event_count` from real event matches against session records; fix any over-restrictive predicate in `_recent_sessions`.
8. Add `/api/sessions/diagnostics` endpoint returning:
   - count of events whose `session_id` matches no session record
   - count of session records whose `event_count` differs from actual joined events
   - sample IDs for both lists
9. Add a CLI surface `opendream sessions diagnose` mirroring the endpoint for offline triage.

## Phase 4 — UI surfaces + cleanup
10. Sessions Timeline: when a session has `event_count == 0`, render a small warning chip linking to the diagnostics doc.
11. Add `opendream sessions cleanup --orphans` to delete or merge orphan event/session records under operator confirmation.
12. Document the invariant in `CONSTITUTION.md` (each emitted event must have a `session_id` resolvable to a session record).

## Verification
- unit test: `current_session_id()` returns identical value across nested calls within a hook span
- integration test: simulate full hook → context → retrieval → run → hook flow; assert single session record with correct `event_count`
- diagnostics test: seed orphan events; assert `/api/sessions/diagnostics` reports them; cleanup removes them
- regression: existing tests using `session_id="…"` literals still pass after migration

## Rollout + rollback
- Phase 1+2 ship together; Phase 3 ships only after invariant tests pass on dogfood data
- rollback: revert minter; old call sites still functional since the API shape is unchanged
- migrate orphan/empty sessions in user data via `opendream sessions cleanup --orphans` (opt-in)
