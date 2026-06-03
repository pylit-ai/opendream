# Global AGENTS example

Reference only. Canonical policy remains in repo `AGENTS.md`, `README.md`, and `docs/`.

Global durable preferences:
`opendream init --workspace ~/.opendream-global --store-kind global`

Route durable user preferences:
`opendream emit-event --workspace "$PWD" --route global --global-workspace ~/.opendream-global --scope global --kind preference_signal --content "$OPENDREAM_SUMMARY" --message-ref "$OPENDREAM_REF"`
