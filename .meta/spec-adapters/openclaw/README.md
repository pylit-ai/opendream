# OpenClaw adapter pack

Canonical behavior lives in `specs/404-framework-adapter-pack/`, `specs/405-layered-memory-stores/`,
`specs/418-transcript-native-dream-engine/`, `specs/420-truthful-verification-and-release/`,
`specs/430-sota-dream-runtime-bundle/`, and `README.md`.
This folder only maps that CLI into OpenClaw prompts and hook examples.

1. Wire `event-map.md` into planner and worker hooks.
2. Copy prompt snippets into your OpenClaw templates.
3. Set `OPENDREAM_WORKSPACE` and optional `OPENDREAM_GLOBAL_WORKSPACE`.

Pre-plan hook:
`sh .meta/spec-adapters/openclaw/scripts/opendream-hooks.sh pre-plan "current task"`

Post-task hook plus a one-shot dream worker poll:
`sh .meta/spec-adapters/openclaw/scripts/opendream-hooks.sh post-task "task summary"`
