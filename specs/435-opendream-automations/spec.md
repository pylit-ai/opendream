# spec.md — 435-opendream-automations

## Title
Add OpenDream automations as managed projection jobs on top of the existing memory runtime

## Why
OpenDream already has durable memory, scheduler-safe `tick`, service lifecycle, and background worker primitives. What it does not have is a separate, reviewable layer for recurring jobs that maintain feature backlogs, bug radar, or other typed projections without polluting canonical durable memory.

This change adds that automation layer. Automations remain local-first, auditable, and bounded, while reusing the existing runtime surfaces instead of inventing a second daemon model.

## In scope
- canonical automation job specs with trigger, selector, policy, and output metadata
- separate automation storage for jobs, run state, typed output records, and audits
- deterministic automation execution over existing OpenDream durable memory
- `opendream automation ...` CLI commands for register, run, tick, status, and review
- top-level `tick`, `status`, and `prepare-context` integration with automation summaries
- canonical `435` spec bundle plus matching proposal-stage OpenSpec bundle committed to the repo

## Out of scope
- executing arbitrary `SKILL.md` or shell commands on a schedule
- vendor-native automation adapters for Codex, Cursor, Claude Code, or Gemini
- background mutation of repository product code
- remote control planes or hosted schedulers

## User-visible behavior
- operators can register a schema-valid automation job under the workspace memory root
- `opendream automation run --job <id>` executes one managed projection job and writes typed records plus audit output
- `opendream automation tick` reuses scheduler-style cadence rules to run due jobs safely
- `opendream status` reports automation health alongside activation and memory runtime state
- `opendream prepare-context` can surface active automation records without merging them into canonical durable memory

## Acceptance criteria
- [x] AC-1: automation jobs persist as schema-valid specs with explicit trigger, selector, policy, and review fields
- [x] AC-2: automation runs write only inside the workspace memory root and emit machine-readable run reports
- [x] AC-3: automation records live in a separate typed store from durable memory and preserve provenance to source memories
- [x] AC-4: top-level `tick` and `status` expose automation work without breaking existing memory or dream flows
- [x] AC-5: `prepare-context` can include active automation projections as a clearly separate section
- [x] AC-6: automated verification covers registration, execution, dedupe or staleness behavior, and top-level status integration

## Edge cases
- duplicate projection candidates across multiple source memories
- disabled jobs, jobs that are not yet due, and jobs with no matching input
- stale projection records after source memories stop matching
- uninitialized workspaces and stores with no durable memories yet

## Required verifiers
- unit tests: yes, deterministic coverage for storage, runtime, and CLI behavior
- integration tests: yes, CLI status and tick flows with automation-enabled stores
- evals / scenario checks: no new eval corpus in this slice
- manual verification: yes, register an automation job in a sample workspace and confirm status plus context output

## Risks
- automation summaries could drift from underlying durable memory if dedupe and staleness rules are weak
- broad selectors could surface noisy projections unless automation outputs stay visibly separate from canonical memory
- top-level status could become harder to read if automation summaries are too verbose

## Links
- `../406-scheduler-and-status-surface/spec.md`
- `../432-first-party-service-lifecycle/spec.md`
- `../434-zero-touch-activation-and-command-surface-compression/spec.md`
