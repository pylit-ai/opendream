# CONSTITUTION

## Purpose
This document defines non-negotiable engineering, safety, and delivery rules for this repository.
If any spec, plan, or implementation conflicts with this constitution, the constitution wins.

## Article 0 — Product trust
1. OpenDream exists to improve long-horizon agent reliability without weakening operator control.
2. If a design increases autonomy by reducing auditability or reversibility, the design is wrong unless explicitly approved.
3. Local-first, inspectable behavior is the default; hidden remote state is not.

## Article I — Correctness
1. No feature is complete without automated verification.
2. Every externally visible behavior change MUST be covered by tests or an explicit verifier.
3. Silent fallbacks are forbidden unless explicitly documented in spec and user-facing behavior.

## Article II — Simplicity
1. Prefer the simplest design that satisfies the spec.
2. New abstractions require written justification in the plan.
3. Duplicate patterns should be consolidated before inventing a framework.

## Article III — Change discipline
1. Non-trivial work MUST begin with `spec.md`, `plan.md`, and `tasks.md`.
2. Specs define desired behavior; plans define technical approach; tasks define execution order.
3. Implementation without an approved spec is permitted only for trivial changes:
   - typo
   - comment
   - dependency patch
   - formatting-only change
   - test-only change that does not alter behavior

## Article IV — Safety and security
1. Least privilege by default for credentials, tools, and network access.
2. Secrets MUST NOT be committed, logged, or embedded in examples.
3. Destructive actions require explicit approval paths in AGENTS.md and relevant specs.
4. All external integrations MUST document authentication model, failure modes, and revocation path.
5. Sensitive values MUST NOT be promoted into durable memory unless an explicit allowlist and review path exist.

## Article IV.a — Memory integrity
1. Durable memory mutations MUST preserve provenance.
2. Contradictions MUST NOT be silently overwritten.
3. Background memory maintenance MUST NOT modify repository product code unless a spec explicitly expands that boundary.
4. Startup memory MUST remain compact enough to be reviewed and reasoned about by an operator.

## Article V — Observability
1. All production-impacting flows MUST emit structured logs.
2. Background or asynchronous operations MUST expose state transitions.
3. Failures MUST be diagnosable without reading model prompts.

## Article VI — Testing
1. Unit tests are required for deterministic logic.
2. Integration tests are required for external boundaries.
3. Agentic or workflow behavior MUST define evals or acceptance checks when nondeterminism matters.
4. A passing build, lint, and test suite is required before merge.

## Article VII — Documentation
1. NORTHSTAR.md owns product intent.
2. CONSTITUTION.md owns enduring rules.
3. AGENTS.md owns agent entrypoint and routing.
4. Specs own change-specific details.
5. Architecture docs own enduring technical structure, not task-level instructions.
6. A concept has exactly one canonical home; do not duplicate policy in adapter files.

## Article VIII — Human control
1. Human approval is required for:
   - schema/data migrations
   - production config changes
   - auth/security policy changes
   - billing-affecting changes
   - destructive data operations
2. Agents must stop and surface uncertainty when approval is required.

## Article IX — Decision records
1. Material architectural decisions MUST be captured as ADRs.
2. If an implementation deviates from the plan, the plan or ADR must be updated.

## Amendment policy
This constitution should change rarely.
Any amendment must explain:
- what changed
- why the old rule was insufficient
- what enforcement or verification changes follow
