# Release gates

## Activation
- [x] `opendream init --activate-configured` or `opendream activate` installs working managed surfaces
- [x] no standard-path target requires manual copying from `.meta/`

## Runtime
- [x] pre-task context injection works automatically
- [x] post-task capture, maintain, and queue drain work automatically

## Repair
- [x] `doctor --surface agents` detects drift
- [x] `activate --repair` restores valid state

## Safety
- [x] unrelated config content is preserved
- [x] wrapper mode preserves underlying agent exit status

## E2E
- [x] Claude Code fixture passes
- [x] Codex fixture passes
- [x] OpenClaw fixture passes
