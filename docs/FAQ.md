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
- **Hybrid / semantic dream pipeline**: With `semantic_config.json` set to `hybrid` or `semantic` and a valid provider registry, `dream run` can execute the extended learned-context pipeline (anticipation, synthesis, verification, promotion). **In the current stdlib-only implementation, synthesis and semantic verification use in-process heuristics**; provider entries and API keys drive **availability and health checks** ahead of future outbound LLM transports. Learned-context proposals still pass through verification before promotion.
- **No vector database**: Retrieval uses hybrid lexical + semantic scoring without external dependencies.
- **No code mutation**: OpenDream reads and remembers — it does not modify your codebase.
- **No cross-project memory by default**: Each project has its own store. Global memory is opt-in via `--store-kind global`.

## Is it local-first / private?

Yes for **data**: artifacts stay under your workspace memory root (default `.opendream/memory/`). The default **deterministic** consolidation and **automation** paths do not open network connections from this package. **Optional** semantic provider configuration is intended for future outbound API calls to your chosen vendor; today the bundled semantic path still runs **without** those calls (heuristic synthesis/verification). The observability UI listens on `localhost` only when you start it. Operators: [semantic-mode-and-feature-radar-setup.md](automation/semantic-mode-and-feature-radar-setup.md).

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

**Q: Do I need extra API keys for semantic mode?**

A: Not always. If you have Codex, Claude, or Cursor installed, `opendream semantic setup --prefer no-extra-key` will recommend an account-backed or vendor-delegated path that requires no additional API key. If none are available, you can use `--prefer direct-provider` with an explicit Anthropic or OpenAI API key. Gemini CLI OAuth reuse is not supported.

## What is semantic sleep-time mode?

Semantic mode adds an extended **learned-context pipeline** (anticipation, proposal synthesis, verification, promotion) on top of dreaming and retrieval. Configuration uses providers and execution strategies (API key, Codex account, or vendor-delegated Claude/Cursor). **In the current stdlib-only core, transcript `dream run --mode hybrid|semantic` still uses in-process heuristics for synthesis/verification**; providers mainly gate availability and health until outbound transports land. **Live model work** for backlog refresh is expected in **Layer C** (your agent session or delegated `semantic ingest`). See [complete-operator-workflow.md](automation/complete-operator-workflow.md) §1 and §3–4 for the exact split.

Semantic mode is optional. Without `semantic_config.json` (or with `"mode": "deterministic"`), the store behaves like deterministic-only for semantic **availability**. Use `opendream semantic config --workspace "$PWD"` and `opendream semantic status --workspace "$PWD"` to inspect configuration; see [semantic-mode-and-feature-radar-setup.md](automation/semantic-mode-and-feature-radar-setup.md) for file paths and a full setup sequence.

Use `opendream semantic setup --workspace "$PWD"` to detect available execution strategies and get a clear recommendation.

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
