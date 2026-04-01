# test-matrix.md — 439-memory-excellence-release-bundle

| Area | Scenario | Type | Expected |
|---|---|---|---|
| boundary | dream worker attempts non-memory write | integration | blocked with explicit report |
| boundary | semantic worker attempts non-memory write | integration | blocked with explicit report |
| verify-before-assert | count/path/framework claim without evidence | unit/integration | downgraded or quarantined |
| verify-before-assert | concrete claim with bounded verification read | integration | promoted with verification provenance |
| transcript probing | probe hits then bounded read | integration | small contextual read only |
| transcript probing | no hit | integration | no bulk episode load |
| compat views | manual drift between durable state and MEMORY.md | integration | regeneration or verification failure |
| relations | supersession edge changes retrieval ranking | unit/integration | superseded item demoted |
| relations | contradiction cluster in review UI | integration | explicit conflict explanation visible |
| reconciliation | renamed project root / orphan view | integration | detected and repaired audibly |
| reconciliation | stale topic file with missing support | integration | downgraded/quarantined or regenerated |
| procedural memory | workflow with recovery steps | integration | reused in later task context |
| eval | stale-claim seeded corpus | e2e | stale-claim rate below budget |
| eval | contradiction seeded corpus | e2e | contradiction resolution accuracy at threshold |
| eval | repeated coding tasks | e2e | full system beats append-only and no-memory baselines |
| concurrency | overlapping remember + dream + reconcile | e2e | one lock holder, no corruption, no lost work |
| docs | forbidden misleading wording | unit | wording gate catches it |
| release | make verify + make release-check | e2e | all gates pass |
