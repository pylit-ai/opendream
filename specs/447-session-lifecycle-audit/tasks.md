# Tasks

## P0 — audit + docs
- [ ] catalog every session_id mint/emit site across the codebase
- [ ] author `docs/architecture/session-lifecycle.md` with sequence diagram
- [ ] enumerate gaps with file/line citations

## P0 — canonical minter
- [ ] add `opendream.sessions.current_session_id()` backed by contextvar + workspace token file
- [ ] update claude-pre-task / codex-pre-task hooks to set contextvar + token
- [ ] update post-task hooks to clear contextvar + token
- [ ] migrate every emit path to read canonical session_id
- [ ] remove ad-hoc minting; add lint to forbid `uuid4()` near session_id assignments

## P0 — aggregator correctness
- [ ] re-derive `event_count` from join; fix over-restrictive filters
- [ ] add `/api/sessions/diagnostics` with orphan + mismatch reports
- [ ] add `opendream sessions diagnose` CLI

## P0 — verification
- [ ] unit: `current_session_id()` stable across nested calls in a hook span
- [ ] integration: full hook → context → retrieval → run → hook produces 1 session record with correct count
- [ ] diagnostics: seeded orphans surface in endpoint; cleanup removes them
- [ ] regression: existing tests still pass post-migration

## P1 — UI + cleanup
- [ ] Sessions row: warning chip when `event_count == 0` with link to docs
- [ ] `opendream sessions cleanup --orphans` with confirm prompt + dry-run
- [ ] `CONSTITUTION.md` invariant: every emitted event resolves to a session record
