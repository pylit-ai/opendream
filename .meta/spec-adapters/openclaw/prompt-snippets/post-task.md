# OpenClaw post-task snippet

Reference only. Canonical behavior remains in `README.md` and `specs/403-406`.

Record the outcome:
`opendream-memory emit-event --workspace "$OPENDREAM_WORKSPACE" --kind task_outcome --content "$OPENCLAW_SUMMARY" --message-ref "$OPENCLAW_REF"`

Run maintenance:
`opendream-memory tick --workspace "$OPENDREAM_WORKSPACE" --include-global --global-workspace "$OPENDREAM_GLOBAL_WORKSPACE"`
