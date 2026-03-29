# Release gates

Stable release is blocked unless:
- configured supported targets activate without manual `.meta/` copying
- status provides enough information for the normal path
- repair fixes drift in one command
- deactivate removes managed surfaces without damaging unrelated content
