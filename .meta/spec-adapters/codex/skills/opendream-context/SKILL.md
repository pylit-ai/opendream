# OpenDream Context

Reference only. Canonical rules stay in `README.md`, `CONSTITUTION.md`, and `specs/403-406`.

Before planning:
`opendream-memory status --workspace "$OPENDREAM_WORKSPACE"`

Inject prompt-ready memory:
`opendream-memory prepare-context --workspace "$OPENDREAM_WORKSPACE" --query "$OPENDREAM_QUERY"`

After a task:
`opendream-memory tick --workspace "$OPENDREAM_WORKSPACE"`
