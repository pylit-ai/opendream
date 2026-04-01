# release-gates.md — 439-memory-excellence-release-bundle

A release candidate is blocked unless all gates below pass.

## RG-1 Runtime memory-only boundaries
- dream and semantic workers cannot mutate project code or arbitrary repo paths
- no-code-write verification diff shows only memory subtree and bounded audit paths changed
- violations fail the run and are reported explicitly

## RG-2 Verify-before-assert
- externally checkable claims cannot be promoted as active truth without strong provenance or bounded runtime verification
- unverifiable or weakly supported concrete claims are downgraded, hedged, or quarantined
- verification rationale is visible in audit artifacts

## RG-3 Grep-first transcript probing
- transcript gathering uses grep/probe-first by default
- full bulk replay remains disabled by default
- bounded window reads occur only after probe hits or explicit escalation
- probe and escalation budgets are visible in run reports

## RG-4 Generated-only compatibility views
- `MEMORY.md`, `project.md`, and `user.md` are generated-only views
- topic views and indexes regenerate from canonical state
- drift between canonical records and generated markdown fails verification

## RG-5 Contradiction graph and supersession-aware retrieval
- relation edges exist for contradiction, supersession, derivation, and verification
- retrieval/ranking and review surfaces use those relations
- contradictory memories are not silently surfaced as parallel active truth

## RG-6 Reconciliation sweeps
- reconciliation can detect renamed roots, orphan views, stale topic files, missing evidence references, and drifted compatibility artifacts
- repairs are auditable and bounded
- reconciliation never silently destroys provenance history

## RG-7 Procedural memory strength
- procedural memory stores workflow steps plus preconditions, recovery moves, and anti-pattern hints
- repeated coding-task evals show positive procedural reuse impact
- procedural memory remains distinct from generic note summaries

## RG-8 Review and observability
- observability surfaces show verification status, relation edges, probe traces, and reconciliation outcomes
- review UX can explain why a memory is active, contested, superseded, or quarantined

## RG-9 Memory-excellence evals
- release evidence includes a memory-excellence scorecard
- scorecard covers stale-claim prevention, contradiction resolution, irrelevant recall, derivability hygiene, procedural reuse, concurrency safety, and generated-view integrity
- release fails if scorecard thresholds are not met

## RG-10 Docs truthfulness
- README / FAQ / benchmark docs describe the product as a verified, bounded, auditable memory system
- docs do not imply whole-transcript replay or markdown-only canonical memory
