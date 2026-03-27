# spec.md — 406-scheduler-and-status-surface

## Title
Add a cron-safe scheduler tick and operator-visible status surface for OpenDream

## Why
OpenDream has a local memory engine, runtime integration commands, and framework adapter packs. Operators still need a minimal scheduling and status surface so the system can run unattended in a boring, inspectable way. This change adds `tick` and `status` primitives rather than a heavyweight daemon.

## In scope
- `opendream-memory tick`
- `opendream-memory status`
- scheduler policy loading from store config
- multi-store aware ticking
- lock-state and last-run reporting
- README and adapter docs updated to prefer `tick` for cron and hooks

## Out of scope
- resident daemon
- GUI
- remote orchestrator
- background service manager integration beyond examples

## User-visible behavior
- Operators can call `tick` repeatedly from cron, hooks, or wrappers.
- `tick` evaluates maintenance policy and runs or skips cleanly.
- `status` reports whether a store is idle, has pending work, or is currently locked.
- Framework adapters can call `status` before prompting and `tick` after task completion or on cron.

## Acceptance criteria
- [x] AC-1: `opendream-memory status --workspace <path>` returns pending events, pending candidates, last run time, and lock state
- [x] AC-2: `opendream-memory tick --workspace <path>` is safe to call repeatedly and only runs maintenance when policy permits
- [x] AC-3: `tick` supports multi-store manifests when layered stores are enabled
- [x] AC-4: tests cover skip or run transitions, stale lock visibility, and repeated invocation
- [x] AC-5: docs include runnable cron and hook examples using `tick` and `status`

## Edge cases
- stale lock file
- status called before initialization
- tick called while another consolidate run holds the lock
- no new work across all stores
- min-interval suppression

## Required verifiers
- unit tests: yes, status rendering and tick decision logic
- integration tests: yes, repeated tick and lock-state flows
- evals / scenario checks: no
- manual verification: yes, run tick twice, inspect skip; hold a lock, inspect status

## Risks
- status output becomes misleading if it omits pending or lock information
- tick grows into an implicit daemon instead of remaining a thin deterministic wrapper

## Links
- `../../specs/403-runtime-integration-layer/spec.md`
- `../../README.md`
