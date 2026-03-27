# Codex adapter pack

Canonical behavior lives in `specs/403-runtime-integration-layer/`, `specs/404-framework-adapter-pack/`,
`specs/405-layered-memory-stores/`, `specs/406-scheduler-and-status-surface/`, and `README.md`.
This folder only translates that CLI into AGENTS and skill examples.

1. Merge `AGENTS.global.example.md` into your global `AGENTS.md`.
2. Merge `AGENTS.project.snippet.md` into the repo `AGENTS.md`.
3. Install `skills/opendream-context/` if you want an explicit wrapper.
4. Set `OPENDREAM_WORKSPACE` and optional `OPENDREAM_GLOBAL_WORKSPACE`.

Pre-task context:
`sh .meta/spec-adapters/codex/scripts/opendream-pre-task.sh "current task"`

Post-task maintenance:
`sh .meta/spec-adapters/codex/scripts/opendream-post-task.sh "task summary"`
