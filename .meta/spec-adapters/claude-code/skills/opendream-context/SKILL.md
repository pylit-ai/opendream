# OpenDream Context

Reference only. Canonical rules stay in `README.md`, `CONSTITUTION.md`, and `specs/403-406`.

Before planning:
`opendream-memory prepare-context --workspace "$OPENDREAM_WORKSPACE" --query "$OPENDREAM_QUERY"`

Before prompting:
`opendream-memory status --workspace "$OPENDREAM_WORKSPACE"`

After a task:
`opendream-memory maintain --workspace "$OPENDREAM_WORKSPACE"`

For durable user preferences:
`opendream-memory emit-event --workspace "$OPENDREAM_WORKSPACE" --route global --global-workspace "$OPENDREAM_GLOBAL_WORKSPACE" --scope global --kind preference_signal --content "$OPENDREAM_SUMMARY" --message-ref "$OPENDREAM_REF"`
