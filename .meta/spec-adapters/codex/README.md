# Codex adapter pack

Canonical behavior lives in `README.md`, `docs/architecture/`, `docs/adr/`, and `opendream/schema/`.
This folder only translates that CLI into AGENTS and skill examples.

1. Prefer `opendream init --workspace "$PWD" --activate-configured` for the standard path.
2. Use `opendream status --workspace "$PWD"` for the compressed health view, then `opendream activate --workspace "$PWD" --repair` if drift appears.
3. Use `AGENTS.global.example.md`, `AGENTS.project.snippet.md`, and `skills/opendream-context/` only as non-normative examples.
4. Set `OPENDREAM_WORKSPACE` and optional `OPENDREAM_GLOBAL_WORKSPACE`.
5. Use `opendream deactivate --workspace "$PWD"` to remove managed repo-local surfaces.

Pre-task context:
`sh .meta/spec-adapters/codex/scripts/opendream-pre-task.sh "current task"`

Post-task maintenance plus a one-shot dream worker poll:
`sh .meta/spec-adapters/codex/scripts/opendream-post-task.sh "task summary"`
