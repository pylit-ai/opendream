# 437-semantic-sleep-time-release-bundle

## Why

OpenDream now has a credible transcript-native DreamRunner, layered memory stores, automation projections, review tooling, release gates, and agent-ready packaging surfaces. However, the current release story still admits a decisive parity gap: the project documents deterministic consolidation and explicitly lacks model-backed semantic consolidation. That is incompatible with a strong AutoDream-performance claim because the strongest publicly supported mechanism behind sleep-time compute is offline semantic anticipation and rewriting of memory for likely future query families.

The next release must therefore stop treating model-backed semantic memory as deferred future work. Instead, semantic sleep-time memory must become a first-class, audited, benchmarked, release-blocking capability that coexists with the deterministic path but is no longer absent from the product surface.

This bundle turns semantic sleep-time memory into a complete release program:
- hybrid deterministic + semantic dreaming,
- a distinct learned-context layer,
- anticipation of likely future query families,
- proposal / verification / promotion contracts,
- retrieval fusion,
- benchmark integration using MemoryAgentBench-style competencies,
- coding-task evals that measure actual throughput and memory-hurt,
- meta-harness-inspired harness optimization,
- license/provenance hygiene for external reference artifacts,
- and updated release evidence that blocks ship if the semantic mode is incomplete or unproven.

## What Changes

- add a first-class **semantic sleep-time mode** to the DreamRunner
- add a new **learned-context** memory layer separate from typed durable fact/procedural records
- add an **anticipation planner** that predicts likely future query families and optimizes offline synthesis for them
- add a **semantic verifier + promotion** path so model outputs do not become canonical truth without audit and checks
- fuse learned context into retrieval and prompt injection with attribution, freshness, and harm controls
- integrate **MemoryAgentBench-style** competencies and task adapters into the benchmark suite
- add realistic repeated coding-task evals that measure success, latency, cost, irrelevant recall, contradiction recovery, and memory-hurt
- add a **meta-harness** capability for environment bootstrap and harness optimization loops
- add license/provenance rules so Sleep-time Compute code may be reused only where allowed and MemoryAgentBench / Meta-Harness artifacts are treated clean-room unless explicit redistribution rights are confirmed
- update documentation, README/FAQ/benchmarks, release gates, and package behavior so semantic mode is a release requirement rather than future work

## Capabilities

### New Capabilities
- `semantic-sleep-time-mode`: model-backed offline memory synthesis integrated into DreamRunner
- `learned-context-layer`: versioned semantic memory blocks with provenance, freshness, and conflict metadata
- `anticipation-planner`: likely future query-family inference and offline precompute targeting
- `semantic-verifier-promotion`: proposal-only semantic writes with deterministic + model-backed verification before promotion
- `retrieval-fusion`: combined retrieval over durable facts, procedural memory, learned context, and automation projections
- `benchmark-suite`: unified semantic-memory benchmark runner with internal fixtures, MemoryAgentBench-style competencies, and coding-task evals
- `memoryagentbench-integration`: clean-room adapters and scoring for AR / TTL / LRU / CR-style measurements
- `coding-task-evals`: repeated coding-task task-success / cost / latency / memory-hurt benchmark suite
- `meta-harness-optimization`: environment bootstrap plus offline harness search / ablation surface for memory injection and retrieval policy optimization
- `licensing-provenance`: enforceable reuse policy and attribution flow for third-party code/prompts/data

### Modified Capabilities
- `418-transcript-native-dream-engine`: add semantic phase extensions and learned-context outputs
- `430-sota-dream-runtime-bundle`: planner / verifier / queue-backed worker extended to semantic jobs
- `435-opendream-automations`: semantic refresh, strategist jobs, and learned-context-backed automations
- `436-agent-ready-platform-complete`: engine registry and package outputs updated to include semantic mode surfaces and benchmark commands
- `420-truthful-verification-and-release`: semantic benchmark gates become mandatory for release

## Non-goals

- vague “LLM mode” bolted onto current rules without contracts
- silent replacement of typed durable memory with free-form summaries
- unrestricted third-party prompt/code copying
- mandatory cloud hosting
- mandatory specific model vendor
- product-code mutation from unattended semantic jobs without isolation, approval, and audit
- optimizing only for benchmark scores while ignoring memory-hurt or auditability

## Success criteria

- OpenDream ships with a fully implemented, documented, tested semantic sleep-time mode.
- Hybrid mode (deterministic + semantic) is supported and benchmarked; deterministic-only remains as a fallback, not the flagship capability.
- Learned context is stored separately from canonical durable records and is attributable, freshness-aware, reviewable, and retrievable.
- Semantic jobs use proposal → verification → promotion contracts; no direct unaudited mutation path exists.
- Release verification fails if semantic mode is absent, unsafe, unbenchmarked, or materially worse than deterministic baseline.
- External benchmark integration and coding-task evals are reproducible enough for release evidence, even where third-party code is not vendored.
- README / FAQ / benchmark docs no longer describe model-backed consolidation as absent in the release candidate.
