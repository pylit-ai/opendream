# spec.md — 433-zero-touch-agent-activation

## Title
Add zero-touch agent activation, repair, and drift-aware managed surfaces

## Why
OpenDream already ships durable memory, queued dream work, and first-party service lifecycle controls. The missing product layer is activation ownership: operators still have to translate documentation, hook examples, and autowire commands into live agent configuration by hand.

This change makes supported repo-local agents activate from a first-party OpenDream command. It installs managed native surfaces where available, falls back to a repo-local wrapper where needed, and adds drift-aware doctor and repair flows.

## In scope
- `opendream activate`
- `opendream doctor --surface agents`
- `opendream init --activate-configured`
- detection and persistence of supported agent targets under `.opendream/`
- managed surfaces for Claude Code, Codex, and OpenClaw
- activation and repair reports plus schemas
- drift detection and repair verification
- canonical `433` spec bundle plus matching proposal-stage OpenSpec bundle committed to the repo

## Out of scope
- hosted orchestration or hidden remote control
- destructive overwrite of unrelated agent configuration
- cloud-managed plugin channels
- background service installation when post-task queue drain is already sufficient

## User-visible behavior
- `opendream activate --workspace <path>` detects configured supported agents and installs managed surfaces
- `opendream init --workspace <path> --activate-configured` initializes memory and immediately activates configured agents
- `opendream doctor --workspace <path> --surface agents` explains detected targets, activation state, drift, and repairability
- `opendream activate --workspace <path> --repair` restores missing or drifted managed surfaces and emits a machine-readable repair report

## Acceptance criteria
- [x] AC-1: activation installs working managed surfaces for configured Claude Code, Codex, and OpenClaw fixtures without manual copying from `.meta/`
- [x] AC-2: activation remains idempotent and preserves unrelated content in AGENTS and JSON config files
- [x] AC-3: Codex activation installs a repo-local wrapper path and that wrapper preserves the underlying command exit code
- [x] AC-4: `doctor --surface agents` detects missing or drifted managed surfaces and `activate --repair` restores them
- [x] AC-5: release and packaging smoke exercise activation, repair, and runtime hook behavior for supported targets

## Edge cases
- workspace has no supported configured agents
- managed blocks already exist with unrelated surrounding content
- a generated hook file is deleted while the registry still claims activation
- a target is unsupported or absent and should not be marked broken

## Required verifiers
- unit tests: yes, CLI integration coverage for activation, repair, and wrapper exit semantics
- integration tests: yes, packaging smoke and release smoke for activation flows
- evals / scenario checks: yes, `make verify` and `make release-check`
- manual verification: yes, run `opendream init --activate-configured`, inspect `.opendream/`, and trigger the generated hooks in a temp workspace

## Risks
- Codex does not expose first-class native lifecycle hooks, so the AGENTS plus wrapper path must stay explicit and inspectable
- managed JSON hook edits must remain narrow so unrelated user configuration survives repeated activation

## Links
- `../432-first-party-service-lifecycle/spec.md`
- `../404-framework-adapter-pack/spec.md`
- `../../notepads/active/simplify.md`
