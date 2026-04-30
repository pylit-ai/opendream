# Session lifecycle (audit + remediation plan)

Spec: 447-session-lifecycle-audit.

## Symptom
Most session records in `Observe → Sessions` show `event_count = 0` or `1`. Every retrieval and emit appears to mint a fresh `session_id` rather than reusing the agent's active session.

## Audit findings (as of 2026-04-29)

### Independent mint sites
- `opendream/integration.py:267` — `emit_event` computes
  `computed_session_id = session_id or stable_id("session", event_timestamp, store.store_kind, scope)`.
  Different timestamps → different session_ids; passing `session_id=None` shards the same agent span.
- `opendream/integration.py:992` — context retrieval mints
  `stable_id("session", query)` from the **query string**.
  Two retrievals with different queries land in different sessions even within
  one agent task.
- `opendream/episodes.py:108` — episode reducer mints
  `stable_id("session", row.get("session_id", "dream"), speaker)`.
- `opendream/webapp.py:228` — health/live-check uses constant
  `session-observe-live-check` (intentional, OK).
- `opendream/cli.py:398, 520` — pass-through from caller payload (correct
  behavior; depends on the caller having a session_id at all).

### Effect
Each call site that mints independently fragments one logical agent span into
many one-event sessions. The aggregator in `_recent_sessions` accurately reports
what is in the events log, so the bug is upstream in minting, not aggregation.

## Required event flow (target)

```
claude-pre-task hook ──┐
                       │  set session_id token
codex-pre-task hook  ──┘  (workspace-local + contextvar)
                            │
                            ▼
            ┌────────────────────────────────┐
            │ current_session_id() helper    │
            │  - reads contextvar            │
            │  - falls back to workspace     │
            │    token file                  │
            │  - falls back to time-bucketed │
            │    seed (last resort, logged)  │
            └────────────────────────────────┘
                            │
                            ▼
   emit_event ──┐    retrieve ──┐    run lifecycle ──┐
                │               │                    │
                ▼               ▼                    ▼
                ──── observability events log ────
                            │
                            ▼
                _recent_sessions aggregator
                            │
                            ▼
                    /api/sessions
```

## Remediation plan (per spec 447 plan.md)

### Phase 1 — single canonical minter (this audit + module)
1. Add `opendream/sessions.py` with:
   - `current_session_id() -> str | None` reading a contextvar
   - `set_session_id(value)` writing the contextvar + workspace token
   - `clear_session_id()` clearing both
   - `_workspace_token_path(store)` location (`.opendream/active_session`)
2. Update `claude-pre-task` and `codex-pre-task` hooks to call `set_session_id`.
3. Update `claude-post-task` and `codex-post-task` hooks to call `clear_session_id`.

### Phase 2 — migrate emit paths
4. `integration.emit_event`: replace ad-hoc `stable_id` minting with
   `current_session_id() or stable_id("session", event_timestamp, ...)`.
5. `integration.retrieve` (line 992 area): same; never mint from query.
6. `episodes.reducer`: same; episode/dream emission must inherit, not invent.
7. Add a lint check (custom rule) that flags new `stable_id("session", ...)` usages
   outside `opendream/sessions.py`.

### Phase 3 — aggregator integrity
8. Add `/api/sessions/diagnostics` returning:
   - `orphan_events` — events whose `session_id` matches no session record
   - `mismatch_records` — sessions whose `event_count` ≠ joined event count
   - sample IDs (≤ 25) for each
9. Add `opendream sessions diagnose` CLI mirroring the endpoint.

### Phase 4 — cleanup + UI
10. Add `opendream sessions cleanup --orphans [--dry-run]` to merge or delete
    orphan + zero-event records. Always require explicit confirmation.
11. Sessions row UI: warning chip when `event_count == 0`; link to this doc.
12. Add invariant to `CONSTITUTION.md`: every emitted event must have a
    `session_id` resolvable to a session record.

## Verification
- unit: `current_session_id()` is stable across nested calls within one hook span
- integration: full hook → context → retrieval → run → hook produces exactly
  one session record with `event_count` matching emitted event count
- regression: existing tests that pass explicit `session_id="…"` still pass
- diagnostics: seeded orphans surface in the new endpoint and are removable
- e2e: in a fresh dogfood workspace, `event_count == 0` count is zero across
  all sessions in `/api/sessions`

## Rollback
- minter helper is additive; legacy code paths still work
- if migration introduces regressions, revert call-site updates and ship
  Phase 3 diagnostics standalone — they are read-only and reveal the problem
  without changing behavior
