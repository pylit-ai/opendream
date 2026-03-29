# spec.md — 434-zero-touch-activation-and-command-surface-compression

## Title
Compress the normal OpenDream contract to init, activate, status, repair, and deactivate

## Why
OpenDream now has enough runtime machinery that the main product problem is exposure, not capability. The repo still teaches the operator about dream workers, daemons, autowire flows, hook scripts, and service lifecycle details even when the common path should just be: initialize, activate, check status, repair drift, and optionally remove managed integration.

This change keeps the existing runtime machinery for power users and CI, but compresses the top-level contract so normal usage feels like a managed capability rather than a toolkit of moving parts.

## In scope
- compressed primary CLI and help surface
- `opendream deactivate`
- aggregated top-level `opendream status`
- status and activation state schemas
- target registry persistence for compressed status
- migration and compatibility messaging for older service and autowire paths
- README and adapter docs rewritten to the compressed contract
- canonical `434` spec bundle plus matching proposal-stage OpenSpec bundle committed to the repo

## Out of scope
- removing advanced `dream`, `service`, or `observe` commands
- hosted orchestration
- removing diagnosability for CI or operators
- breaking the activation runtime introduced by `433`

## User-visible behavior
- `opendream init --workspace <path> --activate-configured` is the standard entrypoint
- `opendream activate --workspace <path>` remains the canonical integration command and `--repair` remains the one-command repair path
- `opendream status --workspace <path>` answers activation, drift, queue, and service health in one high-signal response
- `opendream deactivate --workspace <path>` removes managed activation surfaces and leaves the workspace in an inactive but inspectable state

## Acceptance criteria
- [ ] AC-1: `opendream --help` and README promote `init --activate-configured`, `activate`, `status`, `activate --repair`, and `deactivate` as the normal path
- [ ] AC-2: `status` aggregates activation, runtime, queue, and service state and recommends one next action when unhealthy
- [ ] AC-3: `deactivate` removes managed activation surfaces for supported targets without overwriting unrelated user content
- [ ] AC-4: older service and autowire surfaces remain functional but point operators toward the compressed primary commands
- [ ] AC-5: release and fixture verification prove the standard path works for configured Claude Code, Codex, and OpenClaw targets without `.meta/` script copying

## Edge cases
- workspace has no configured supported targets
- workspace has activated targets but inactive runtime health
- deactivation runs on a workspace that was never activated
- status runs on a workspace with both drifted activation and idle queue state

## Required verifiers
- unit tests: yes, CLI integration coverage for status aggregation, deactivate, and migration hints
- integration tests: yes, packaging smoke and release smoke for the compressed standard path
- evals / scenario checks: yes, `make verify` and `make release-check`
- manual verification: yes, run init/activate/status/repair/deactivate in a temp workspace with supported target config

## Risks
- compressing the surface without keeping advanced commands available would strand power users and CI
- status aggregation must stay truthful and not hide important runtime detail behind a misleading healthy summary

## Links
- `../433-zero-touch-agent-activation/spec.md`
- `../432-first-party-service-lifecycle/spec.md`
- `../../notepads/active/simplify2.md`
