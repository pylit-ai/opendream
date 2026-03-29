# spec.md — 432-first-party-service-lifecycle

## Title
Add first-party service lifecycle, worker health, and adapter autowire for unattended OpenDream operation

## Why
OpenDream already ships a queue-backed dream worker, planner and verifier audits, and adapter examples. The missing product layer is lifecycle management: operators still need to hand-install background services, reason about stuck workers manually, and copy hook glue into supported runtimes by hand.

This change adds a first-party lifecycle surface so OpenDream can render installable service manifests, track worker health, diagnose failures, and wire common adapters with reversible managed changes.

## In scope
- `install-service`, `uninstall-service`, and `update-service`
- `service start|stop|restart|status|doctor|autowire`
- launchd and systemd manifest rendering from package templates
- durable worker heartbeat and service runtime state under the memory root
- machine-readable install and autowire reports plus new schemas
- release smoke and CLI integration coverage for lifecycle and autowire flows
- canonical `432` spec bundle plus matching proposal-stage OpenSpec bundle committed to the repo

## Out of scope
- hosted orchestration or remote telemetry
- hidden background services without an explicit operator command
- replacing the existing dream worker queue semantics
- privileged system-wide installs by default

## User-visible behavior
- `opendream install-service` renders and installs a service manifest for the current workspace
- `opendream service status` and `opendream service doctor` expose install state, runtime health, backlog, and remediation
- dream workers persist heartbeat metadata so stale, stopped, or crash-looping services are diagnosable
- `opendream service autowire` configures supported adapter glue idempotently and records what changed

## Acceptance criteria
- [x] AC-1: `install-service` writes schema-valid manifest and install-report artifacts and repeated installs stay idempotent
- [x] AC-2: `service start|stop|restart|status|doctor` accurately reflect a managed worker lifecycle and queue backlog
- [x] AC-3: dream workers persist schema-valid heartbeat state with pid, timestamps, backlog, restart count, and recent failures
- [x] AC-4: supported adapter autowire operations are reversible, idempotent, and machine-reportable
- [x] AC-5: release smoke covers install, status, restart, stop, uninstall, and autowire flows without touching unrelated workspace files

## Edge cases
- service installed but worker process missing
- stale heartbeat while queue backlog grows
- native supervisor install requested on paths or modes that require elevated privileges
- rerunning autowire in a workspace that already has custom hooks or AGENTS content

## Required verifiers
- unit tests: yes, CLI integration coverage for lifecycle status, doctor, and autowire behavior
- integration tests: yes, packaging smoke for service install, restart, stop, uninstall, and autowire
- evals / scenario checks: yes, `make verify` and `make release-check`
- manual verification: yes, install a managed or native service in a sample workspace and confirm doctor output

## Risks
- native supervisor commands remain platform-specific and may need operator privileges in system mode
- adapter autowire touches workspace-local config, so changes must stay narrowly scoped and reversible

## Links
- `../430-sota-dream-runtime-bundle/spec.md`
- `../../notepads/active/reliability.md`
