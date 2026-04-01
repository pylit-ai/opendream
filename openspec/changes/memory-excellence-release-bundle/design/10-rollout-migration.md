# 10-rollout-migration.md

## Rollout order
1. schemas and boundary enforcement
2. claim verification
3. grep-first probe planner
4. index discipline and generated-only views
5. relation edges
6. reconciliation sweeps
7. procedural memory enhancements
8. observability/review UX
9. scorecard and release gates
10. docs and positioning cleanup

## Migration
- existing durable state remains valid
- generated compat views may be rewritten
- new relation edges may be backfilled lazily
- older records missing provenance tiers default conservatively and are eligible for reconciliation

## Release positioning
Describe the product as:
- bounded
- verified
- auditable
- relation-aware
- local-first

Do not describe it as:
- whole-transcript replay
- markdown-only canonical memory
- hidden background magic
