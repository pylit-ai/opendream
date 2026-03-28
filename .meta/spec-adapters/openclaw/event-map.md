# OpenClaw event map

Reference only. Canonical semantics remain in `specs/403-406`.

- `planner.pre_plan` -> `sh .meta/spec-adapters/openclaw/scripts/opendream-hooks.sh pre-plan "$OPENCLAW_TASK"`
- `worker.post_task` -> `sh .meta/spec-adapters/openclaw/scripts/opendream-hooks.sh post-task "$OPENCLAW_SUMMARY"`
- `memory.project_decision` -> `opendream emit-event --workspace "$OPENDREAM_WORKSPACE" --kind project_decision --content "$OPENCLAW_SUMMARY" --message-ref "$OPENCLAW_REF"`
- `memory.preference` -> `opendream emit-event --workspace "$OPENDREAM_WORKSPACE" --route global --global-workspace "$OPENDREAM_GLOBAL_WORKSPACE" --scope global --kind preference_signal --content "$OPENCLAW_SUMMARY" --message-ref "$OPENCLAW_REF"`
