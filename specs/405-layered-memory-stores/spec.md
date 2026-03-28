# spec.md — 405-layered-memory-stores

## Title
Add layered global and project memory stores with precedence-aware retrieval and event routing

## Why
The runtime supported typed scopes in schemas, but storage and retrieval were effectively workspace-local. Operators need project-local durable memory for repo-specific facts and user-global durable memory for persistent preferences across repos.

## In scope
- explicit store kinds:
  - project store
  - global store
- deterministic precedence for retrieval
- deterministic routing policy for emitted events
- cross-store `prepare-context`
- cross-store `maintain`
- configurable global store root
- tests and docs for layered retrieval and conflict handling

## Out of scope
- remote sync
- cloud multi-user memory
- database federation
- semantic vector retrieval

## User-visible behavior
- Operators can initialize a project store and a global store independently.
- Operators can retrieve context from a single store or a composed store group.
- Project-local memory outranks global memory by default.
- Events can be explicitly routed to the project or global store.
- Framework adapters can call one command and receive precedence-aware composed context.

## Acceptance criteria
- [x] AC-1: `opendream init --workspace <repo>` continues to initialize a project store
- [x] AC-2: `opendream init --workspace ~/.opendream-global --store-kind global` initializes a global store
- [x] AC-3: `prepare-context` supports multiple stores and returns precedence-aware merged context
- [x] AC-4: `maintain` supports multiple stores or a store-group manifest
- [x] AC-5: routing defaults preserve project-local isolation unless the operator opts into global routing
- [x] AC-6: tests cover project-over-global precedence, conflict resolution, and no-work skip behavior across stores
- [x] AC-7: docs include runnable examples for `~` plus repo-local usage

## Edge cases
- same key exists in both global and project stores
- project decisions conflict with a global preference
- missing global store
- global store exists but should be excluded for a given task
- accidental secret promotion into the global store

## Required verifiers
- unit tests: yes, precedence and routing logic
- integration tests: yes, multi-store CLI flows
- evals / scenario checks: no
- manual verification: yes, create both `~/.opendream-global` and `.tmp/repo`, then retrieve from both

## Risks
- over-eager global memory pollutes project context
- operators confuse scope labels with actual store routing
- conflict rules become inconsistent if precedence is not explicit

## Links
- `../../PRD.md`
- `../../specs/403-runtime-integration-layer/spec.md`
- `../../docs/adr/ADR-002-layered-memory-store-precedence.md`
- `../../README.md`
