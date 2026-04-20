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

Semantic-first is the default **posture**, but posture and readiness are different. Setting `mode=semantic` does **not** by itself mean the workspace is semantic-ready. If the semantic path has not been applied yet, the truthful state is **setup required**. If a previously applied path is no longer runnable, the truthful state is **degraded semantic-first** with a reason and a next action, while deterministic capture remains available as an explicit fallback.

Semantic mode is optional. Without `semantic_config.json` (or with `"mode": "deterministic"`), the store behaves like deterministic-only for semantic **availability**. Use `opendream semantic config --workspace "$PWD"` and `opendream semantic status --workspace "$PWD"` to inspect configuration; see [semantic-mode-and-feature-radar-setup.md](automation/semantic-mode-and-feature-radar-setup.md) for file paths and a full setup sequence.

Use `opendream semantic setup --workspace "$PWD" --apply` to detect available execution strategies, apply the recommendation, scaffold the path it needs, and run an immediate validation cycle. If you want to re-check later without changing config, use `opendream dream worker --workspace "$PWD" --once --mode auto`.

## What is learned context?

Learned context is a separate mutable memory layer for model-generated semantic abstractions. Unlike durable memory (which is extracted deterministically from evidence), learned context records are synthesized by the semantic dreamer and must pass through a proposal → verify → promote pipeline before being surfaced in retrieval. Learned context records carry provenance (source events, model, prompt version), confidence scores, freshness windows, and conflict state. They are non-canonical until explicitly promoted.

## How do benchmarks work with semantic mode?

OpenDream's benchmark suite has three tiers:

1. **Internal fixtures**: Controlled tests for query-family anticipation, stale abstraction detection, contradiction handling, and memory-hurt adversarial cases.
2. **MemoryAgentBench-style adapters**: Clean-room implementations measuring Accurate Retrieval (AR), Test-Time Learning (TTL), Long-Range Understanding (LRU), and Conflict Resolution (CR).
3. **Coding-task evals**: Repeated task evaluations measuring pass rate, retrieval latency, irrelevant recall, contradiction recovery, procedural reuse, and memory-hurt rate.

Run with `opendream eval semantic-benchmark --workspace .tmp/eval --mode hybrid`. The semantic-first contract is not just "LLM mode ran": release evidence is expected to compare degraded fallback, unpruned baseline behavior, and semantic-ready progressive disclosure. See [docs/benchmarks/semantic-mode.md](benchmarks/semantic-mode.md) for the pruning and repeated-task proof expectations, and [THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md) for provenance of benchmark concepts.

## What does progressive disclosure mean in practice?

It means `prepare-context` should not dump broad history into every prompt. Startup context should stay pointer-like, task context should expand only when relevance warrants it, and the JSON/UI evidence should show what was selected, what was suppressed, and how much budget was saved by pruning.

## What counts as poor semantic memory quality?

OpenDream treats some failure modes as warnings, not hidden implementation details. Examples include:

- semantic-first posture with no runnable semantic path
- durable memory dominated by one low-signal type such as `semantic_fact`
- little or no learned-context activity across the observation window
- ephemera-heavy promoted memory with weak pruning benefit

Those warnings belong in status/doctor/UI surfaces because a workspace that looks semantic on paper can still be low-signal in practice.

## How do I see all my OpenDream workspaces?

OpenDream keeps a **machine-local workspace catalog** at
`~/.opendream/catalog.json`. It is a derived convenience index — the
workspace itself (`<repo>/.opendream/`) remains canonical.

```bash
opendream workspace list                            # every known workspace
opendream workspace roots add --path ~/src          # teach the catalog where to look
opendream workspace scan --all-roots                # explicit, opt-in scan
opendream workspace inspect --workspace ~/src/app
opendream workspace doctor --workspace ~/src/app
opendream workspace forget --workspace ~/src/gone   # removes only the index entry
```

`workspace list` defaults to a human-readable table; pass `--format json`
for machine output. Override the catalog location with
`OPENDREAM_CATALOG_HOME=<dir>`, or disable catalog writes entirely with
`OPENDREAM_CATALOG_DISABLE=1`. The local web UI exposes the same index at
`/workspaces`. There is no whole-home scan, no background crawl, and no
remote sync — every discovery step is operator-initiated. See
[ADR-017](adr/ADR-017-machine-local-workspace-catalog.md) for the
derived-not-canonical rule.

## I upgraded OpenDream in a workspace I was already running — what do I do?

Your workspace-local `.opendream/` state is canonical and survives the
upgrade. After installing the new version:

```bash
pip install -U opendream
opendream workspace upgrade --workspace "$PWD"
```

`workspace upgrade` repairs managed surfaces when needed, re-probes the
workspace, ensures the managed background runtime for project workspaces unless
you have explicitly disabled it, and upserts its catalog entry so the upgraded
repo shows up in `opendream workspace list` and the `/workspaces` dashboard.
The workspace directory is never rewritten by catalog operations. Use
`opendream service disable --workspace "$PWD"` if a repo should stay manual,
and `opendream service enable --workspace "$PWD"` to restore the primary
ongoing-improvement path.

## I have existing workspaces that aren't showing up in `workspace list` — how do I add them?

The catalog only tracks workspaces it has been told about (via `init`,
`activate`, `install-service`, explicit `workspace doctor`, or an opt-in
scan). To backfill existing repos:

```bash
# Bulk: configure scan roots once, scan on demand.
opendream workspace roots add --path ~/src
opendream workspace scan --all-roots

# Or: register one workspace explicitly.
opendream workspace doctor --workspace ~/src/project-a

# Refresh every known entry at once.
opendream workspace doctor --all
```

Scans are depth-bounded and prune noisy directories. If an entry points at
a repo you've since deleted, `workspace forget --workspace <path>` removes
the index entry without touching anything else.

## How do I get started?

```bash
uv tool install opendream   # or: pipx install opendream
opendream init --workspace "$PWD" --activate-configured
opendream status --workspace "$PWD"
```

See the [README](../README.md) quickstart for the full walkthrough.
