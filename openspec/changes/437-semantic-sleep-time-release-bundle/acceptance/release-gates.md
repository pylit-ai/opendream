# release-gates.md — 437-semantic-sleep-time-release-bundle

Release is blocked unless all gates below pass.

## RG-1 Semantic mode exists
- `opendream dream run|tick|worker` support deterministic, semantic, and hybrid modes
- hybrid mode works with explicit provider config
- `dream status` exposes active mode, last semantic run summary, provider id, and promotion outcome counts

## RG-2 Learned-context layer exists
- learned-context records are persisted separately from durable fact/procedural records
- each learned-context record has provenance, freshness, conflict metadata, query-family tags, provider/model identity, and verifier outcome
- learned-context exports are generated from canonical learned-context state, not hand-edited

## RG-3 Proposal / verification / promotion path exists
- semantic outputs are proposal-only by default
- deterministic and semantic verifiers can both veto promotion
- canonical durable memory cannot be silently overwritten by semantic outputs
- promotion decisions are auditable and reversible

## RG-4 Retrieval fusion exists and is attributable
- retrieval can distinguish:
  - durable fact memory
  - procedural memory
  - learned context
  - automation projections
- prompt injection surfaces source attribution and freshness
- gating and harm controls can suppress stale or contradicted learned context

## RG-5 Query-family anticipation exists
- semantic dream runs infer likely future query families
- learned-context outputs are tagged to anticipated query families
- benchmark suites can score whether anticipation improves downstream task performance or cost

## RG-6 Benchmark suite exists
- internal fixture suite runs deterministic-only, semantic-only, and hybrid modes
- MemoryAgentBench-style competencies are measured through clean-room adapters
- repeated coding-task evals measure pass rate, cost, latency, irrelevant recall, contradiction recovery, and memory-hurt
- benchmark outputs are machine-readable and archived in release evidence

## RG-7 Release thresholds are met
- hybrid mode beats deterministic-only on the bundled internal weighted scorecard by >= 5 points
- hybrid mode beats deterministic-only on at least 3 of 4 MemoryAgentBench-style competencies with no >2 point regression on the remaining competency
- hybrid mode improves repeated coding-task utility (success, success@cost, or success@latency) over deterministic-only
- memory-hurt rate remains below the configured budget and is not worse than deterministic-only by more than the configured tolerance

## RG-8 Harness optimization surfaces exist
- environment bootstrap can be enabled and tested
- harness optimization reports are schema-valid and reproducible on smoke tasks
- release does not require a long autonomous search, but the capability, reports, and ablations exist and pass smoke verification

## RG-9 License / provenance hygiene passes
- any vendored Sleep-time Compute code or prompts carry MIT notice and source provenance
- MemoryAgentBench and Meta-Harness code are not vendored unless an explicit redistributable license is confirmed and recorded
- clean-room adapters and benchmark/task specs document which parts are conceptual references vs copied artifacts

## RG-10 Documentation and package truthfulness
- README, FAQ, benchmark docs, and release notes no longer claim that model-backed consolidation is absent in the release candidate
- docs describe hybrid/semantic mode accurately, including limitations and fallback behavior
- package smoke and contract export include semantic mode commands and schemas
