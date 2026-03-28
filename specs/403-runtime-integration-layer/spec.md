# spec.md — 403-runtime-integration-layer

## Title
Add the thin integration layer around the OpenDream memory engine

## Why
OpenDream now has a working local memory engine, but practical day-to-day use still requires too much manual orchestration. The next step is a thin layer that lets a runtime emit events directly, call a cron-safe maintenance command, and inject selected memory into the next task context without inventing a larger daemon.

## In scope
- direct CLI event emission from runtime-friendly flags
- a maintenance wrapper that safely runs extract plus consolidate on repeated cron or idle hooks
- a retrieval adapter that renders prompt-ready context from startup memory and selected durable records
- tests and README updates for the integration path

## Out of scope
- a long-running daemon or background service
- embedding/vector retrieval
- repo-specific orchestration plugins beyond a generic CLI contract

## User-visible behavior
- Operators and runtimes can emit a single memory event without constructing a JSONL file by hand.
- A scheduler can call a single maintenance command repeatedly and get deterministic skip or run behavior.
- A planner can request prompt-ready memory context for the next task rather than stitching together raw JSON manually.

## Acceptance criteria
- [x] AC-1: `opendream emit-event ...` appends a valid schema-compliant event directly to the workspace store
- [x] AC-2: `opendream maintain --workspace <path>` runs extract plus consolidate when work is pending and skips cleanly when nothing new qualifies
- [x] AC-3: `opendream prepare-context --workspace <path> --query "<text>"` returns selected memory ids plus a prompt-ready context block
- [x] AC-4: `make verify` includes automated coverage for event emission, maintenance scheduling behavior, and prompt-context rendering

## Edge cases
- repeated cron calls with no new events
- maintenance runs suppressed by a minimum interval
- prompt context excluding contested memory by default

## Required verifiers
- unit tests: yes, maintenance decision and prompt rendering logic
- integration tests: yes, CLI emission and maintenance flows
- evals / scenario checks: no
- manual verification: yes, run `opendream emit-event`, `maintain`, and `prepare-context` in a temp workspace

## Risks
- prompt-context rendering can become noisy if it dumps too much memory
- a maintenance wrapper that is too eager can surprise operators expecting purely manual flow

## Links
- `../../specs/401-autodream-style-memory-subsystem/spec.md`
- `../../README.md`
