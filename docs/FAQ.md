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
- **No model-backed consolidation**: Consolidation uses deterministic rules, not LLM calls. This is intentional for reproducibility and cost.
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
4. **Deterministic consolidation**: Uses rule-based extraction, not LLM-powered. This means consistent results but potentially lower recall on ambiguous signals.
5. **Memory can hurt**: In some scenarios, stale or contradicted memories could degrade agent performance. The memory-hurt audit tracks this but mitigation is still evolving.

## How are benchmarks run?

```bash
opendream eval performance --workspace .tmp/eval
```

The scorecard covers write precision (20%), retrieval precision (20%), latency (15%), concurrency safety (15%), contradiction handling (10%), procedural reuse (10%), and gating accuracy (10%). Pass threshold: weighted total >= 80. See [docs/benchmarks/methodology.md](benchmarks/methodology.md) for full details.

## How do I get started?

```bash
uv tool install opendream   # or: pipx install opendream
opendream init --workspace "$PWD" --activate-configured
opendream status --workspace "$PWD"
```

See the [README](../README.md) quickstart for the full walkthrough.
