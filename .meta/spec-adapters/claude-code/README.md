# Claude Code adapter pack

Canonical behavior lives in `specs/404-framework-adapter-pack/`, `specs/405-layered-memory-stores/`,
`specs/418-transcript-native-dream-engine/`, `specs/420-truthful-verification-and-release/`,
`specs/430-sota-dream-runtime-bundle/`, and `README.md`.
This folder only maps that CLI into Claude Code examples.

1. Prefer `opendream init --workspace "$PWD" --activate-configured` for the standard path.
2. Use `opendream status --workspace "$PWD"` for the compressed health view, then `opendream activate --workspace "$PWD" --repair` if drift appears.
3. Use `hooks/example-settings.json` and `skills/opendream-context/` only as non-normative examples.
4. Set `OPENDREAM_WORKSPACE=/path/to/repo`.
5. Optionally set `OPENDREAM_GLOBAL_WORKSPACE=~/.opendream-global`.
6. Use `opendream deactivate --workspace "$PWD"` to remove managed repo-local surfaces.

Pre-task context:
`sh .meta/spec-adapters/claude-code/scripts/opendream-pre-task.sh "current task"`

Post-task maintenance plus a one-shot dream worker poll:
`sh .meta/spec-adapters/claude-code/scripts/opendream-post-task.sh "task summary"`
