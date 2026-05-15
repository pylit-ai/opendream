# OpenDream Context

Reference only. Canonical rules stay in `README.md`, `AGENTS.md`, and `docs/`.

Before planning:
`opendream status --workspace "$OPENDREAM_WORKSPACE"`

Inject prompt-ready memory:
`opendream prepare-context --workspace "$OPENDREAM_WORKSPACE" --query "$OPENDREAM_QUERY"`

After a task:
`opendream maintain --workspace "$OPENDREAM_WORKSPACE"`
