# 04-semantic-verifier-and-promotion.md

## Principle
Semantic outputs are **proposals first**.

## Verification pipeline

### deterministic verifier
Checks:
- required fields present
- provenance exists
- timestamps normalized
- source coverage threshold met
- no disallowed sensitive spill
- no direct contradiction with stronger durable facts without explicit conflict flag
- no duplicate or near-duplicate spam

### semantic verifier
Checks:
- source-groundedness
- no unsupported extrapolation
- compression usefulness
- query-family relevance
- contradiction treatment quality
- removal of unhelpful or stale detail

### promotion rules
- if both verifiers pass => promote to learned-context layer
- if semantic output is sufficiently source-grounded and maps to an allowed durable schema => optional distillation into typed durable candidate, never direct overwrite
- if either verifier fails => store rejected proposal artifact only
- if verifier confidence is mixed => downgrade freshness or require manual review

## Review surfaces
- proposal list
- verifier rationale
- conflict visualizations
- promotion diffs
- reversal / reject / supersede actions
