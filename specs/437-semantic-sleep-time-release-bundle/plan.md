# plan.md — 437-semantic-sleep-time-release-bundle

## Summary

Implement a complete semantic sleep-time release on top of the current OpenDream runtime. Preserve the existing deterministic, local-first, auditable architecture, but add a model-backed semantic path that:
1. anticipates likely future query families,
2. synthesizes learned context offline,
3. verifies and promotes outputs through explicit contracts,
4. fuses semantic memory into retrieval and automation,
5. and proves value through benchmark suites that include both benchmark-style competencies and realistic coding-task outcomes.

This is a release-blocking change bundle, not an experimental appendix.

## Architecture impact

### Touched components
- `opendream/dream.py`
- `opendream/episodes.py`
- `opendream/consolidator.py`
- `opendream/retriever.py`
- `opendream/storage.py`
- `opendream/evaluation.py`
- `opendream/automation.py`
- `opendream/cli.py`
- `opendream/models.py`
- `opendream/validation.py`
- `opendream/observability.py`
- `opendream/contract_export.py`
- `opendream/webapp.py`
- `docs/FAQ.md`
- `docs/architecture/overview.md`
- `docs/benchmarks/*`
- `docs/automation/*`
- `README.md`
- `tests/*`
- release scripts and verification runners

### New modules expected
- `opendream/semantic_dreamer.py`
- `opendream/semantic_verifier.py`
- `opendream/query_families.py`
- `opendream/provider_registry.py`
- `opendream/benchmark_adapters.py`
- `opendream/harness_optimizer.py`

### New persisted artifacts expected
- learned-context state and audit files
- semantic dream reports
- benchmark run reports
- memory-hurt attribution reports
- harness optimization reports
- third-party provenance / attribution docs

## Data model / contract changes
- add `learned_context_records.json` or equivalent canonical storage subtree
- add learned-context markdown / compat exports only as generated views
- extend dream run reports with semantic phases, provider ids, verifier decisions, query-family coverage, and harm metrics
- add provider config schema
- add semantic dream config schema
- add benchmark run schemas
- add harness optimization report schema
- extend contract export to include semantic commands / schemas / modes

## Interfaces
- new CLI family for semantic dreaming, benchmark execution, harness optimization, and provenance reporting
- updated `dream run|tick|status|worker` behavior to support semantic mode
- updated `prepare-context` behavior to optionally inject learned context with attribution
- updated eval and release commands so semantic gates are no longer optional

## Observability
- dream reports expose deterministic + semantic phase timings, query families, provider/model, verifier findings, selected source evidence, and promoted record ids
- retrieval reports distinguish durable facts vs procedural memory vs learned context vs automation projections
- benchmark reports archive deterministic-only, semantic-only, and hybrid comparisons
- memory-hurt reports classify harm source into write-path, retrieval-path, learned-context, or reasoning-layer buckets
- harness optimization reports store proposals, scores, traces, and selected winning variants

## Security / safety review
- no new hidden network paths; all provider use must be explicit through configuration
- semantic mode must preserve no-code-write guarantees unless a separate isolated automation job explicitly opts into code mutation
- learned context must remain non-canonical until promoted and must not silently override stronger durable facts
- any vendored third-party code or prompt text must pass provenance and license checks
- benchmark runners that reference third-party repositories without explicit licenses must use clean-room adapters instead of vendored code

## Rollout
1. land schemas, storage model, and CLI contracts
2. land provider abstraction and semantic dreamer core
3. land verifier / promotion path and retrieval fusion
4. land semantic automation jobs and context injection
5. land benchmark adapters, internal eval corpora, and release gates
6. land meta-harness bootstrap / optimizer surfaces
7. update docs, package smoke, contract export, and release evidence
8. run full verification and release matrix

## Rollback
1. disable semantic mode in config and CLI entrypoints
2. preserve learned-context artifacts for inspection but stop injection and promotion
3. fall back to deterministic DreamRunner and current release gates
4. retain docs clarifying hybrid mode disablement if rollback happens after public preview

## Verification plan
- schema validation for all new artifacts
- deterministic unit tests for provider-independent logic
- integration tests for semantic dream runs, verifier blocking, promotion, retrieval fusion, and automation jobs
- benchmark smoke tests for internal corpora and MemoryAgentBench-style adapters
- coding-task eval smoke tests with multiple modes
- harness bootstrap and optimization smoke tests
- `make verify` and `make release-check` must fail honestly if semantic mode thresholds are not met

## ADRs required
- semantic learned-context layer
- semantic verifier / promotion policy
- hybrid retrieval and injection rules
- benchmark and harness optimization architecture
- third-party provenance and reuse policy
