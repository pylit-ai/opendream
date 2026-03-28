# OpenClaw pre-plan snippet

Reference only. Canonical behavior remains in `README.md` and `specs/403-406`.

Before planning:
`opendream status --workspace "$OPENDREAM_WORKSPACE"`

Inject memory:
`opendream prepare-context --workspace "$OPENDREAM_WORKSPACE" --query "$OPENCLAW_TASK" --include-global --global-workspace "$OPENDREAM_GLOBAL_WORKSPACE"`
