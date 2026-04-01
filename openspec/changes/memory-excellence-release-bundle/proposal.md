# 439-memory-excellence-release-bundle

## Why

OpenDream already has a strong local-first memory runtime: layered stores, compact startup memory, topic views, transcript-native dreaming, typed durable records, contradiction states, procedural memory, audit trails, and release verification. That foundation is good enough to avoid imitation. The next release must therefore do something harder and more valuable: turn OpenDream into a memory system that is not merely compact and convenient, but **truthful, bandwidth-disciplined, contradiction-aware, and operationally auditable under real long-horizon coding workloads**.

To do that, the next phase must close seven gaps:

1. Memory-only write boundaries are a rule, but not yet an enforced runtime contract everywhere they need to be.
2. Concrete claims can still be synthesized without a strong enough verify-before-assert discipline.
3. Transcript access is bounded, but not yet fully optimized around grep-first / bounded-window probing.
4. The startup index is compact, but it must become even more explicitly pointer-like and regenerated-only.
5. Contradiction and supersession exist, but they are not yet central enough to retrieval ranking and review UX.
6. Staleness, renames, orphaned views, and memory-root drift need a dedicated reconciliation sweep.
7. Release proof must directly demonstrate that all of the above outperform note-like memory systems on repeated coding tasks.

This bundle makes those properties release-blocking.

## Goal

Ship a release-ready “memory excellence” layer that preserves OpenDream’s typed, auditable core while adding:
- enforced memory-only runtime boundaries,
- verified writes for externally checkable claims,
- grep-first transcript probing with bounded-window reads,
- stricter pointer-index discipline and generated-only compatibility views,
- contradiction-graph and supersession-aware retrieval,
- reconciliation sweeps for staleness / orphan / rename drift,
- stronger procedural memory extraction and reuse,
- richer review / observability surfaces,
- and benchmark + release gates that prove the improvements.

## What Changes

- add an enforced memory-maintenance runtime boundary for dream and semantic workers
- add claim verification and provenance-tier gating before concrete claims become active memory
- add grep-first transcript probing and bounded-read escalation
- tighten index generation so `MEMORY.md` is regenerated-only and more pointer-like
- add explicit relation edges and contradiction-graph-aware retrieval/ranking
- add reconciliation sweeps for orphan views, renamed roots, stale topic files, and evidence drift
- elevate procedural memory with stronger workflow representation, preconditions, recovery steps, and reuse signals
- extend observability and review UX around graph relations, verification provenance, and reconciliation outcomes
- add new evals and release gates for stale-claim prevention, contradiction resolution, concurrency safety, grep-first retrieval quality, and repeated coding-task improvement
- update release docs to position OpenDream as a bounded, verified, auditable memory system rather than a note folder

## Non-goals

- replacing the typed durable store with markdown-only topic files
- whole-corpus transcript replay as the default runtime strategy
- hidden memory mutation
- generic graph-database adoption as a prerequisite
- broad repository mutation during memory maintenance
- importing third-party code or prompt text to implement runtime behavior
- weakening existing auditability in pursuit of “cleaner UX”

## Success criteria

- dream and semantic workers are runtime-constrained to memory-only writes and bounded read scopes
- concrete memory claims are verified before promotion or are explicitly hedged/quarantined
- transcript access uses grep-first probing and bounded-window reads by default
- `MEMORY.md`, `project.md`, and `user.md` remain generated views, not canonical state
- contradiction/supersession edges influence retrieval, review, and promotion decisions
- reconciliation sweeps can detect and repair stale/orphan/rename drift without silently rewriting truth
- release verification proves that the full system improves repeated coding-task outcomes while keeping stale-claim and irrelevant-recall rates within budget
