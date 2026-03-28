# spec.md — 410-truthful-verification

## Title
Truthful verification and adversarial quality gates

## Why
The repo currently overclaims verification. `typecheck` is only syntax compilation, `lint` is a narrow whitespace pass, and the release narrative is stronger than the evidence. This change makes verification honest, inspectable, and deterministic.

## In scope
- real static analysis with checked-in configuration
- real lint with checked-in configuration
- deterministic verification orchestration and verdict reporting
- schema and property-style validation for core memory contracts
- inspectable write summaries and diffs for memory mutations
- README and release language aligned to the actual gate

## Out of scope
- hosted CI policy
- external SaaS quality platforms
- non-memory product direction changes

## User-visible behavior
- `make verify` runs real lint, real type analysis, tests, packaging smoke, and adversarial probes.
- Verification emits a machine-readable verdict artifact rather than only stdout.
- Memory writes and consolidations leave behind auditable summaries and diffs.

## Acceptance criteria
- [ ] AC-1: introducing an intentional type error causes `make verify` to fail
- [ ] AC-2: introducing an intentional lint violation causes `make verify` to fail
- [ ] AC-3: introducing a schema-invalid memory payload causes tests to fail
- [ ] AC-4: consolidation and direct memory writes emit a JSON summary plus a human-readable diff artifact
- [ ] AC-5: the verifier emits a deterministic `verification_report.json`

## Edge cases
- tool dependencies missing from a fresh machine
- docs claiming readiness that the gate does not prove
- mutations that touch state but skip an audit artifact

## Required verifiers
- unit tests: yes, verification contract and write-audit contract
- integration tests: yes, failing probe coverage and CLI write transparency
- evals / scenario checks: yes, adversarial probe stage in the verification runner
- manual verification: yes, run `make verify` and inspect the emitted report

## Risks
- stricter static analysis may surface latent issues that require code cleanup
- verification can become slow if orchestration is careless

## Links
- `../../README.md`
- `../../specs/401-autodream-style-memory-subsystem/spec.md`
