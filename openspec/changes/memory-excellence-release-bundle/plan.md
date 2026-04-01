# plan.md — 439-memory-excellence-release-bundle

## Summary

Implement a complete “memory excellence” layer that pushes OpenDream beyond note-oriented memory systems. Preserve the current typed, auditable, local-first architecture, but add stronger runtime boundaries, verified claims, grep-first transcript access, relation-aware retrieval, reconciliation sweeps, procedural-memory upgrades, richer review tooling, and release-blocking evaluation.

This is a release bundle, not a research memo.

## Architecture impact

### Touched components
- `opendream/dream.py`
- `opendream/episodes.py`
- `opendream/planner.py`
- `opendream/retriever.py`
- `opendream/consolidator.py`
- `opendream/extractor.py`
- `opendream/storage.py`
- `opendream/validation.py`
- `opendream/models.py`
- `opendream/observability.py`
- `opendream/webapp.py`
- `opendream/evaluation.py`
- `opendream/cli.py`
- `opendream/contract_export.py`
- `scripts/verify.py`
- `scripts/release_check.py`
- `docs/architecture/overview.md`
- `docs/FAQ.md`
- `docs/benchmarks/methodology.md`
- `docs/benchmarks/autodream-comparison.md`
- relevant review/observability docs and README sections

### New major surfaces
- memory-boundary enforcement layer
- claim verification / provenance-tier classifier
- transcript probe planner and probe reports
- contradiction-graph relation store
- reconciliation sweep runner and reports
- procedural-memory enrichment surfaces
- memory-excellence scorecard and release gate
- observability panels for verification, graph edges, and reconciliation

### Unchanged fundamentals
- durable typed records remain canonical
- topic markdown and compatibility views remain generated
- transcript replay remains bounded
- memory maintenance remains local-first and auditable
- no direct code writes from background memory workers

## Data model / contract changes
- add relation-edge schema for contradiction, supersession, derivation, and verification edges
- add claim-verification report schema and provenance tiers
- add transcript-probe report schema
- add reconciliation report schema
- add memory-excellence scorecard schema
- extend durable records or sidecar metadata with stronger claim provenance state
- extend contract export with new commands and report types

## Interfaces
- new CLI surfaces for verification, transcript probes, and reconciliation
- extended `dream run|tick|worker|status`
- extended `prepare-context` explanations
- release-check and verify integrate the new scorecard

## Observability
- show verified vs inferred vs quarantined claims
- show relation edges and supersession/contradiction clusters
- show transcript probes and escalation reads
- show reconciliation findings and applied repairs
- show memory-hurt and stale-claim diagnostics

## Security / safety review
- memory workers write only to the memory subtree and bounded audit paths
- probe escalations remain bounded by byte/window budgets
- claim verification never turns missing evidence into silent truth
- graph relations must remain reviewable, not hidden ranking magic
- reconciliation sweeps repair views and stale state without rewriting provenance history

## Rollout
1. land schemas and runtime-boundary enforcement
2. land claim verification and provenance tiers
3. land grep-first probe planner and bounded-window reads
4. land index discipline and generated-only compatibility views
5. land relation edges and graph-aware retrieval/review
6. land reconciliation sweeps
7. land procedural-memory enhancements
8. land observability/review surfaces
9. land evals, thresholds, docs, and release gates

## Rollback
1. disable the new excellence gate
2. keep current typed durable memory and audit model intact
3. fall back to current bounded dream pipeline
4. preserve reports/artifacts for inspection but stop using them in ranking/promotion

## Verification plan
- unit tests for claim verification, probe planning, relation edges, and reconciliation logic
- integration tests for no-code-write runtime boundaries, probe escalation, contradiction ranking, and generated-view discipline
- evals for stale-claim prevention, irrelevant recall, contradiction accuracy, repeated coding-task improvement, and multi-agent concurrency
- release-check archives memory-excellence scorecard and diagnostics

## ADRs required
Yes. Promote enduring decisions on:
- enforced maintenance boundaries
- verified-write policy
- generated-only compatibility views
- contradiction-graph semantics
- reconciliation sweep model
