# plan.md — 412-memory-quality

## Summary
Improve retrieval and consolidation quality without adding external dependencies. Use deterministic hybrid scoring, lightweight semantic vectors, and candidate clustering to promote better recall and safer durable-memory state transitions.

## Architecture impact
- touched components:
  - retrieval scoring and explanation payloads
  - consolidation dedupe and contradiction handling
  - eval fixtures and CLI
  - tests and README examples
- unchanged components:
  - local-first file storage
  - framework adapter boundaries

## Data model / contract changes
- extend retrieval audit payloads with structured explanation sections
- use explicit `quarantined` durable status
- add eval fixture corpus

## Interfaces
- input: `retrieve`, `prepare-context`, and `eval memory-quality`
- output: richer explanations, safer durable statuses, eval metrics

## Observability
- per-factor retrieval score contributions
- merge or conflict decisions in consolidation audit logs

## Security / safety review
- auth changes: none
- secret handling: low-confidence and sensitive signals remain blocked or quarantined
- irreversible actions: none

## Rollout
1. add canonical spec bundle
2. improve retrieval scoring and explanations
3. add dedupe/conflict logic
4. add eval corpus and docs

## Rollback
1. disable embedding-like retrieval path
2. restore simpler lexical ranking

## Verification plan
- run: `python3 -m unittest tests.test_memory_cli tests.test_validation_and_models -v`
- run: `opendream-memory eval memory-quality --workspace <tmp>`
- run: `make verify`

## ADR needed?
- no
