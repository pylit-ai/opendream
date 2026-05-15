# OpenDream Context

Reference only. Canonical rules stay in `README.md`, `AGENTS.md`, and `docs/`.

Before planning:
`opendream prepare-context --workspace "$OPENDREAM_WORKSPACE" --query "$OPENDREAM_QUERY"`

Before prompting:
`opendream status --workspace "$OPENDREAM_WORKSPACE"`

After a task:
`opendream maintain --workspace "$OPENDREAM_WORKSPACE"`

For durable user preferences:
`opendream emit-event --workspace "$OPENDREAM_WORKSPACE" --route global --global-workspace "$OPENDREAM_GLOBAL_WORKSPACE" --scope global --kind preference_signal --content "$OPENDREAM_SUMMARY" --message-ref "$OPENDREAM_REF"`
