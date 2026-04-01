# 09-evals-and-release-thresholds.md

## Goal
Turn the recommended improvements into measurable release evidence.

## Scorecard dimensions
- stale-claim prevention
- contradiction resolution accuracy
- irrelevant recall
- derivability hygiene
- procedural reuse
- concurrency safety
- repeated coding-task improvement
- generated-view integrity

## Suggested release thresholds
- stale-claim rate: 0 in seeded deterministic fixture, and below configured budget in extended fixture
- contradiction resolution accuracy: >= 95% on seeded contradiction corpus
- irrelevant recall: not worse than current release baseline
- repeated coding-task improvement: positive delta vs append-only and no-memory baselines
- no-code-write boundary violations: 0
- generated-view drift: 0

## Philosophy
Release should be blocked by trustworthy memory regressions even if superficial UX still looks good.
