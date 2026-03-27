# Claude Code adapter pack

Canonical behavior lives in `specs/403-runtime-integration-layer/`, `specs/404-framework-adapter-pack/`,
`specs/405-layered-memory-stores/`, `specs/406-scheduler-and-status-surface/`, and `README.md`.
This folder only maps that CLI into Claude Code examples.

1. Copy `hooks/example-settings.json` into your Claude settings.
2. Install `skills/opendream-context/`.
3. Set `OPENDREAM_WORKSPACE=/path/to/repo`.
4. Optionally set `OPENDREAM_GLOBAL_WORKSPACE=~/.opendream-global`.

Pre-task context:
`sh .meta/spec-adapters/claude-code/scripts/opendream-pre-task.sh "current task"`

Post-task maintenance:
`sh .meta/spec-adapters/claude-code/scripts/opendream-post-task.sh "task summary"`
