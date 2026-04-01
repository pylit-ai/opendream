# 07-benchmark-suite.md

## Benchmark tiers

### Tier 1 — Internal deterministic fixtures
- preserve current fixture-driven tests
- add semantic and hybrid variants
- add query-family-targeted cases
- add memory-hurt adversarial cases

### Tier 2 — MemoryAgentBench-style competencies
Measure:
- Accurate Retrieval (AR)
- Test-Time Learning (TTL)
- Long-Range Understanding (LRU)
- Conflict Resolution (CR)

Implement via clean-room adapters and task wrappers, not copied benchmark internals unless redistribution rights are confirmed.

### Tier 3 — Coding-task task suites
Measure:
- task success delta
- latency
- token / cost consumption
- irrelevant recall
- contradiction recovery
- procedural reuse
- memory-hurt

### Tier 4 — Release evidence
- archive machine-readable scorecards
- include ablations:
  - deterministic-only
  - semantic-only
  - hybrid
  - hybrid+bootstrap
  - hybrid+optimized harness (if enabled)

## Benchmark philosophy
The benchmark suite must prove utility, not merely count memories.
