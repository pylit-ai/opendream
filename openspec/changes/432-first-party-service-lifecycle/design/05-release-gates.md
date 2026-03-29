# Release gates

Stable release remains blocked unless:
- install and uninstall are idempotent
- service status and doctor reflect real runtime state
- queue backlog survives restart
- autowire remains reversible and scoped to managed files or blocks
