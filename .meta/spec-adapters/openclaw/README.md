# OpenClaw adapter pack

Canonical behavior lives in `specs/403-runtime-integration-layer/`, `specs/404-framework-adapter-pack/`,
`specs/405-layered-memory-stores/`, `specs/406-scheduler-and-status-surface/`, and `README.md`.
This folder only maps that CLI into OpenClaw prompts and hook examples.

1. Wire `event-map.md` into planner and worker hooks.
2. Copy prompt snippets into your OpenClaw templates.
3. Set `OPENDREAM_WORKSPACE` and optional `OPENDREAM_GLOBAL_WORKSPACE`.

Pre-plan hook:
`sh .meta/spec-adapters/openclaw/scripts/opendream-hooks.sh pre-plan "current task"`

Post-task hook:
`sh .meta/spec-adapters/openclaw/scripts/opendream-hooks.sh post-task "task summary"`
