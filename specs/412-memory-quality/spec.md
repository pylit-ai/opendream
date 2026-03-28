# spec.md — 412-memory-quality

## Title
Upgrade retrieval and consolidation from heuristic MVP to trustworthy memory quality

## Why
The current retrieval path is mostly lexical overlap plus recency, and consolidation only does literal duplicate checks. That is not enough for paraphrases, near-duplicates, contradictions, or low-confidence extractions. This change adds hybrid retrieval, candidate clustering, explicit contradiction states, and a benchmarkable eval surface.

## In scope
- hybrid retrieval with lexical, embedding-like similarity, type, recency, and scope priors
- semantic dedupe and candidate clustering
- explicit `active`, `superseded`, `contested`, and `quarantined` durable statuses
- structured retrieval explanations
- deterministic eval corpus and `opendream-memory eval memory-quality`

## Out of scope
- remote embedding providers
- hosted evaluation dashboards
- cross-machine shared ranking services

## User-visible behavior
- Paraphrased recall works even when literal overlap is weak.
- Retrieval responses explain why each memory was included or excluded.
- Contradictions and low-confidence memories are surfaced honestly instead of silently merged into active truth.

## Acceptance criteria
- [ ] AC-1: a paraphrased query retrieves the correct memory where lexical-only retrieval misses
- [ ] AC-2: contradictory memories are not both surfaced as active without warning
- [ ] AC-3: low-confidence extracted memories do not silently enter durable active state
- [ ] AC-4: retrieval explanations are stable and structured
- [ ] AC-5: consolidation reduces duplicate count on a seeded noisy corpus

## Edge cases
- near-duplicate phrasing from different sources
- low-provenance or stale signals
- scope conflicts between project and global stores
- over-merge versus under-merge tradeoffs

## Required verifiers
- unit tests: yes, retrieval scoring, explanations, and contradiction states
- integration tests: yes, noisy corpus consolidation and eval command
- evals / scenario checks: yes, deterministic memory-quality eval corpus
- manual verification: yes, run `opendream-memory eval memory-quality`

## Risks
- hybrid scoring can become opaque if explanations are not kept in sync
- naive synonym handling can over-merge unrelated records

## Links
- `../../README.md`
- `../../specs/405-layered-memory-stores/spec.md`
