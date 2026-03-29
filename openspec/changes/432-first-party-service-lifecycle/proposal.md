# 432-first-party-service-lifecycle

## Why
OpenDream now has a queue-backed dream runtime, planner and verifier artifacts, and adapter examples. The remaining gap is operational: services still require manual supervisor setup, heartbeat state is thin, and adapters need copy-pasted glue.

## Goal
Make OpenDream easy to run unattended and easy to diagnose when background work stalls.

## Non-goals
- hosted orchestration
- hidden services without an explicit install command
- replacing dream worker internals
- root-required installs by default

## Success criteria
- `opendream install-service` renders a stable service manifest and install report
- `opendream service status` and `opendream service doctor` explain health, backlog, and remediation
- supported adapters can be autowired idempotently and reversed
- release smoke covers install, status, restart, stop, uninstall, and autowire paths
