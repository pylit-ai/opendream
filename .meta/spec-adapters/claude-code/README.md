# Claude Code adapter pack

Canonical behavior lives in `specs/404-framework-adapter-pack/`, `specs/405-layered-memory-stores/`,
`specs/418-transcript-native-dream-engine/`, `specs/420-truthful-verification-and-release/`,
`specs/430-sota-dream-runtime-bundle/`, and `README.md`.
This folder only maps that CLI into Claude Code examples.

1. Copy `hooks/example-settings.json` into your Claude settings.
2. Install `skills/opendream-context/`.
3. Set `OPENDREAM_WORKSPACE=/path/to/repo`.
4. Optionally set `OPENDREAM_GLOBAL_WORKSPACE=~/.opendream-global`.

Pre-task context:
`sh .meta/spec-adapters/claude-code/scripts/opendream-pre-task.sh "current task"`

Post-task maintenance plus a one-shot dream worker poll:
`sh .meta/spec-adapters/claude-code/scripts/opendream-post-task.sh "task summary"`
