# OpenDream FAQ

## What is OpenDream?

OpenDream is a local-first memory subsystem for coding agents. It captures, consolidates, and retrieves project knowledge across sessions so your agent remembers decisions, workflows, environment requirements, and preferences without cloud dependencies.

## What problem does it solve?

Coding agents lose context between sessions. OpenDream provides durable memory with typed records, contradiction handling, and retrieval that gets better over time — so agents stop re-asking questions you already answered.

## How is it different from AutoDream?

AutoDream is Anthropic's built-in memory consolidation for Claude Code. OpenDream differs in several measurable ways:

- **Concurrency safety**: Single-writer file lock vs no locking (AutoDream has a known concurrency issue)
- **Audit trail**: Full diff + plan + verifier per run vs "Writing memory" with no diff
- **Contradiction handling**: Temporal validity windows with superseded/contested status vs unknown mechanism
- **Procedural memory**: Dedicated workflow extraction vs memory file cleanup only
- **Performance measurement**: Composite scorecard with 7 dimensions vs none publicly available
- **Agent breadth**: Works with Claude Code, Codex, Cursor, Gemini, and GitHub Copilot — not locked to one agent

See [docs/benchmarks/autodream-comparison.md](benchmarks/autodream-comparison.md) for the full comparison with evidence citations.

## What does OpenDream NOT do?

- **No cloud storage**: All memory is local. There is no remote sync, hosted service, or telemetry.
- **Hybrid consolidation**: Consolidation defaults to deterministic rules for reproducibility and cost. When semantic mode is enabled with a configured provider, OpenDream can also run model-backed synthesis (sleep-time compute) to generate learned-context abstractions — these remain proposals until promoted through verification.
- **No vector database**: Retrieval uses hybrid lexical + semantic scoring without external dependencies.
- **No code mutation**: OpenDream reads and remembers — it does not modify your codebase.
- **No cross-project memory by default**: Each project has its own store. Global memory is opt-in via `--store-kind global`.

## Is it local-first / private?

Yes. All data stays on your machine under `.opendream/memory/` in your project directory. No network calls are made. No data leaves your filesystem. The observability UI runs on `localhost` only when you explicitly start it.

## What is the license?

OpenDream is currently under a proprietary license (all rights reserved). It is not offered under an open-source license unless the LICENSE file is replaced with an explicit grant. See [LICENSE](../LICENSE) for the exact terms.

## What are the known limitations?

1. **Fixture-driven benchmarks**: Performance evaluation uses controlled fixtures, not diverse real-world repos. Ecological validity is future work.
2. **Small-scale testing**: Current eval uses 5-9 events. Behavior at 1000+ events over months is not benchmarked.
3. **No live AutoDream comparison**: We cannot run AutoDream programmatically, so comparisons are evidence-based, not runtime-based.
4. **Consolidation recall**: Deterministic mode uses rule-based extraction with consistent results but potentially lower recall on ambiguous signals. Hybrid mode adds model-backed synthesis for higher recall, but learned-context outputs require verification before promotion.
5. **Memory can hurt**: In some scenarios, stale or contradicted memories could degrade agent performance. The memory-hurt audit tracks this but mitigation is still evolving.

## How are benchmarks run?

```bash
opendream eval performance --workspace .tmp/eval
```

The scorecard covers write precision (20%), retrieval precision (20%), latency (15%), concurrency safety (15%), contradiction handling (10%), procedural reuse (10%), and gating accuracy (10%). Pass threshold: weighted total >= 80. See [docs/benchmarks/methodology.md](benchmarks/methodology.md) for full details.

## What is semantic sleep-time mode?

Semantic mode adds offline model-backed synthesis to OpenDream's consolidation pipeline. When configured with a provider (e.g. Anthropic, OpenAI), OpenDream can anticipate likely future queries, synthesize learned-context abstractions from transcript evidence, and verify them before promotion. This is inspired by sleep-time compute research — the model "thinks" before queries are asked.

Semantic mode is optional. Without a configured provider, OpenDream runs in deterministic-only mode with no behavioral change from prior versions. Use `opendream semantic config --workspace "$PWD"` and `opendream semantic status --workspace "$PWD"` to inspect and manage configuration.

## What is learned context?

Learned context is a separate mutable memory layer for model-generated semantic abstractions. Unlike durable memory (which is extracted deterministically from evidence), learned context records are synthesized by the semantic dreamer and must pass through a proposal → verify → promote pipeline before being surfaced in retrieval. Learned context records carry provenance (source events, model, prompt version), confidence scores, freshness windows, and conflict state. They are non-canonical until explicitly promoted.

## How do benchmarks work with semantic mode?

OpenDream's benchmark suite has three tiers:

1. **Internal fixtures**: Controlled tests for query-family anticipation, stale abstraction detection, contradiction handling, and memory-hurt adversarial cases.
2. **MemoryAgentBench-style adapters**: Clean-room implementations measuring Accurate Retrieval (AR), Test-Time Learning (TTL), Long-Range Understanding (LRU), and Conflict Resolution (CR).
3. **Coding-task evals**: Repeated task evaluations measuring pass rate, retrieval latency, irrelevant recall, contradiction recovery, procedural reuse, and memory-hurt rate.

Run with `opendream eval semantic-benchmark --workspace .tmp/eval --mode hybrid`. See [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for provenance of benchmark concepts.

## How do I get started?

```bash
uv tool install opendream   # or: pipx install opendream
opendream init --workspace "$PWD" --activate-configured
opendream status --workspace "$PWD"
```

See the [README](../README.md) quickstart for the full walkthrough.
