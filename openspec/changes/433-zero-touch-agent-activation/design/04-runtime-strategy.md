# Runtime strategy

The default activation model is event-driven:
- pre-task hooks call `prepare-context`
- post-task hooks call `emit-event`, `maintain`, and `dream worker --once`

Always-on background services are only required if a future target exposes backlog behavior that cannot be drained safely in post-task hooks.
