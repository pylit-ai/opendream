# Claude Code adapter pack

Canonical behavior lives in `README.md`, `docs/architecture/`, `docs/adr/`, and `opendream/schema/`.
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
